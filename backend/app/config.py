import os
from decimal import Decimal
from math import isfinite
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

FINDINGS_PUBLICATION_RESERVE_SECONDS = 6
FINDINGS_DEADLINE_CONFIGURATION_ERROR = (
    "Invalid backend configuration: AI_FINDINGS_DEADLINE_SECONDS must be finite and greater "
    f"than the {FINDINGS_PUBLICATION_RESERVE_SECONDS}-second publication reserve."
)


def validate_findings_deadline(value: float) -> float:
    if not isfinite(value) or value <= FINDINGS_PUBLICATION_RESERVE_SECONDS:
        raise ValueError(FINDINGS_DEADLINE_CONFIGURATION_ERROR)
    return value


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_url: SecretStr
    public_origin: str = "https://localhost:3000"
    visitor_session_ttl_seconds: int = Field(default=86400, gt=0)
    current_dataset_version: str = "synthetic-payments-v0.1"
    ai_findings_enabled: bool = False
    ai_findings_provider: Literal["mock", "openai"] = "mock"
    openai_api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)
    ai_findings_model: str = "gpt-6-luna"
    ai_findings_max_input_tokens: int = Field(default=12000, gt=0)
    ai_findings_max_output_tokens: int = Field(default=3000, gt=0)
    ai_findings_model_timeout_seconds: float = Field(default=10, gt=0, allow_inf_nan=False)
    ai_findings_count_timeout_seconds: float = Field(default=3, gt=0, allow_inf_nan=False)
    ai_findings_deadline_seconds: float = Field(default=20, gt=0, allow_inf_nan=False)
    ai_findings_max_attempt_usd: Decimal = Field(default=Decimal("0.003"), gt=0)
    ai_findings_max_attempts_per_case: int = Field(default=5, gt=0, le=50)

    @field_validator("ai_findings_deadline_seconds")
    @classmethod
    def require_publication_reserve(cls, value: float) -> float:
        return validate_findings_deadline(value)

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
            settings = cls(
                database_url=os.environ.get("DATABASE_URL", ""),
                public_origin=os.environ.get("PUBLIC_ORIGIN", "https://localhost:3000"),
                visitor_session_ttl_seconds=os.environ.get("VISITOR_SESSION_TTL_SECONDS", "86400"),
                current_dataset_version=os.environ.get(
                    "CURRENT_DATASET_VERSION", "synthetic-payments-v0.1"
                ),
                **{
                    name: os.environ[name.upper()]
                    for name in cls.model_fields
                    if name.startswith("ai_findings_") and name.upper() in os.environ
                },
            )
            if settings.ai_findings_enabled and settings.ai_findings_provider == "openai":
                key = os.environ.get("OPENAI_API_KEY")
                if key:
                    return settings.model_copy(update={"openai_api_key": SecretStr(key)})
            return settings
        except (ValidationError, ValueError) as exc:
            # Never include environment input or connection strings in startup errors.
            if isinstance(exc, ValidationError) and any(
                error["loc"] == ("ai_findings_deadline_seconds",)
                for error in exc.errors(include_input=False)
            ):
                raise RuntimeError(FINDINGS_DEADLINE_CONFIGURATION_ERROR) from None
            raise RuntimeError(
                "Invalid backend configuration; check DATABASE_URL, PUBLIC_ORIGIN, and session TTL"
            ) from None
