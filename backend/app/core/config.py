"""Application settings, loaded from environment / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database (async SQLAlchemy URL). Defaults target the docker-compose `db` service.
    database_url: str = "postgresql+asyncpg://stocky:stocky_dev_password@db:5432/stocky"

    # Admin auth.
    admin_password: str = "change-me"
    jwt_secret: str = "change-me-to-a-long-random-string"
    jwt_expire_minutes: int = 480
    jwt_algorithm: str = "HS256"

    # CORS.
    frontend_origin: str = "http://localhost:3000"

    # Name of the cookie holding the admin session JWT.
    session_cookie: str = "stocky_admin"


settings = Settings()
