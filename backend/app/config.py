import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_url: SecretStr
    public_origin: str = "https://localhost:3000"
    visitor_session_ttl_seconds: int = Field(default=86400, gt=0)

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except ArgumentError:
            raise ValueError("A valid PostgreSQL connection URL is required") from None
        if url.drivername != "postgresql+psycopg" or not url.database:
            raise ValueError("A PostgreSQL database using the psycopg driver is required")
        return value

    @field_validator("public_origin")
    @classmethod
    def require_https_origin(cls, value: str) -> str:
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.path
            or url.query
            or url.fragment
        ):
            raise ValueError("PUBLIC_ORIGIN must be an HTTPS origin without a path")
        # Accessing port also validates its syntax and range.
        _ = url.port
        return value

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
        try:
            return cls(
                database_url=os.environ.get("DATABASE_URL", ""),
                public_origin=os.environ.get("PUBLIC_ORIGIN", "https://localhost:3000"),
                visitor_session_ttl_seconds=os.environ.get("VISITOR_SESSION_TTL_SECONDS", "86400"),
            )
        except (ValidationError, ValueError):
            # Never include environment input or connection strings in startup errors.
            raise RuntimeError(
                "Invalid backend configuration; check DATABASE_URL, PUBLIC_ORIGIN, and session TTL"
            ) from None
