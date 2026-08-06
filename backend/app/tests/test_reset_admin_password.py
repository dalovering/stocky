"""The `make reset-admin-pass` CLI.

The password-writing half is `admin_auth.set_password`, already covered by `test_auth.py`;
what's specific here is the prompting and the guards around it.
"""

from __future__ import annotations

import sys
from collections.abc import Iterator

import pytest

from app import reset_admin_password as cli


@pytest.fixture
def answers(monkeypatch: pytest.MonkeyPatch):
    """Feed scripted replies to the getpass prompts."""

    def _set(*replies: str) -> None:
        it: Iterator[str] = iter(replies)
        monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": next(it))

    return _set


def test_prompt_returns_confirmed_password(answers):
    answers("a-good-password", "a-good-password")
    assert cli._prompt() == "a-good-password"


def test_prompt_rejects_mismatch(answers):
    answers("a-good-password", "a-different-one")
    with pytest.raises(SystemExit, match="did not match"):
        cli._prompt()


def test_prompt_rejects_short_password(answers):
    """Enforced by SetupRequest, so the CLI can't drift from /api/auth/setup."""
    answers("short")
    with pytest.raises(SystemExit, match="at least 8 characters"):
        cli._prompt()


def test_refuses_non_interactive(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(sys, "stdin", type("NotATty", (), {"isatty": lambda self: False})())
    with pytest.raises(SystemExit, match="interactive terminal"):
        cli.main()
