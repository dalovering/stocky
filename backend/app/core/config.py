"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from urllib.parse import quote_plus

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database connection components — the single source of truth for credentials.
    # The async SQLAlchemy URL is assembled from these (see `database_url`), so the
    # password is never duplicated into a URL string in .env.
    # `postgres_host` is `localhost` for host-run commands (make dev/migrate/seed) and is
    # overridden to `db` for the backend container by docker-compose.
    postgres_user: str = "stocky"
    postgres_password: str = "stocky_dev_password"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "stocky"

    # Optional explicit override (e.g. a managed DB). If set, it wins over the components.
    database_url_override: str | None = None

    # Admin auth.
    admin_password: str = "change-me"
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expire_minutes: int = 480
    jwt_algorithm: str = "HS256"

    # CORS.
    frontend_origin: str = "http://localhost:3000"

    # Name of the cookie holding the admin session JWT.
    session_cookie: str = "stocky_admin"

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy URL, assembled from the POSTGRES_* components.

        The password is URL-encoded so special characters don't break the DSN.
        """
        if self.database_url_override:
            return self.database_url_override
        user = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
