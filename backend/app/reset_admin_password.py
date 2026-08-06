"""Set the admin password from the terminal — the recovery path when you're locked out.

The password lives (bcrypt-hashed) in the database, not in `.env`, so there is no file to edit
when it's forgotten. Run with `make reset-admin-pass`.

This sets a new password directly rather than clearing the old one. Clearing would put the app
back into first-launch state, where `POST /api/auth/setup` is open to anyone on the LAN until
somebody claims it; setting it here leaves no such window.
"""

from __future__ import annotations

import asyncio
import getpass
import sys

from pydantic import ValidationError

from app.core.db import async_session_maker
from app.schemas.auth import SetupRequest
from app.services import admin_auth


def _prompt() -> str:
    """Ask for the new password twice, validating it against the API's own setup rule."""
    password = getpass.getpass("New admin password: ")
    try:
        # Reuse the schema so the CLI can't drift from what /api/auth/setup accepts.
        SetupRequest(password=password)
    except ValidationError as exc:
        raise SystemExit(f"Password rejected: {exc.errors()[0]['msg']}") from exc
    if password != getpass.getpass("Confirm new password: "):
        raise SystemExit("Passwords did not match; nothing was changed.")
    return password


async def _reset(password: str) -> None:
    async with async_session_maker() as session:
        replacing = await admin_auth.is_configured(session)
        await admin_auth.set_password(session, password)
    print("Admin password replaced." if replacing else "Admin password set (none was configured).")
    print("Existing admin sessions stay valid — rotate JWT_SECRET and restart to end them.")


def main() -> None:
    if not sys.stdin.isatty():
        raise SystemExit(
            "This command prompts for a password; run it from an interactive terminal."
        )
    asyncio.run(_reset(_prompt()))


if __name__ == "__main__":
    main()
