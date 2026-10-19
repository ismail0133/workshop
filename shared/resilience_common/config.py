"""Explicit file-based secrets; no fallback credentials."""

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import URL


def secret(name: str) -> str:
    value = Path(os.environ[name]).read_text().strip()
    if not value:
        raise RuntimeError(f"Empty secret file: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    service: str
    database_url: URL
    public_key: str
    private_key: str | None
    cursor_key: str | None
    issuer: str = "resilience-alpha-auth"
    audience: str = "resilience-alpha"
    token_seconds: int = 900
    login_rate_limit: int = 5

    @classmethod
    def load(cls, service: str) -> "Settings":
        return cls(
            service=service,
            database_url=database_url(),
            public_key=secret("JWT_PUBLIC_KEY_FILE"),
            private_key=secret("JWT_PRIVATE_KEY_FILE") if service == "auth-service" else None,
            cursor_key=secret("CURSOR_KEY_FILE") if service == "payment-api" else None,
            login_rate_limit=int(os.getenv("LOGIN_RATE_LIMIT", "5")),
        )


def database_url() -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=os.environ["DB_USER"],
        password=secret("DB_PASSWORD_FILE"),
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "resilience"),
    )
