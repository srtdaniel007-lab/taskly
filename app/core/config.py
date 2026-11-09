import os
import re
from typing import Optional
from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "TaskPulse"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    PORT: int = 8000

    # Security & JWT
    SECRET_KEY: str = "super_secret_jwt_key_taskpulse_change_me_in_production_9988776655"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/taskpulse"
    DB_ECHO: bool = False

    # Email / SMTP
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = "notifications@taskpulse.io"
    SMTP_TLS: bool = True

    # Base URL for email notification links
    APP_BASE_URL: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Ensures the database URL is compatible with async SQLAlchemy (asyncpg).
        Render gives URLs like: postgres://... or postgresql://...
        asyncpg requires: postgresql+asyncpg://...
        Also handles sslmode parameters for asyncpg compatibility.
        """
        url = self.DATABASE_URL.strip()
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        # Handle Render's sslmode parameter query string if present
        # asyncpg prefers ?ssl=require rather than ?sslmode=require
        if "sslmode=require" in url:
            url = url.replace("sslmode=require", "ssl=require")

        return url


settings = Settings()
