from collections.abc import Sequence
from typing import Literal

from pydantic import Field, SecretStr, ValidationError
from pydantic_core import ErrorDetails
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "TAPPY_"
PROVIDER_MAX_AMOUNT_CENTS = 100_000_000


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, frozen=True)

    environment: str = Field(min_length=1)
    secret_key: SecretStr = Field(min_length=32)
    database_url: SecretStr = Field(min_length=1)
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    access_token_ttl_seconds: int = Field(default=900, ge=60)
    session_max_lifetime_seconds: int = Field(default=30 * 24 * 3600, ge=3600)
    admin_secure_cookies: bool = True
    payment_provider: Literal["simulated"] = "simulated"
    sale_max_amount_cents: int = Field(
        default=PROVIDER_MAX_AMOUNT_CENTS, ge=1, le=PROVIDER_MAX_AMOUNT_CENTS
    )


class ConfigurationError(Exception):
    pass


def variable_name(location: Sequence[int | str]) -> str:
    field_path = "_".join(str(part) for part in location)
    return f"{ENV_PREFIX}{field_path}".upper()


def is_secret(location: Sequence[int | str]) -> bool:
    field = Settings.model_fields.get(str(location[0])) if location else None
    return field is not None and field.annotation is SecretStr


def safe_message(issue: ErrorDetails) -> str:
    if not is_secret(issue["loc"]) or issue["type"] == "missing":
        return issue["msg"]
    if issue["type"] in {"too_short", "string_too_short"}:
        return f"must have at least {issue.get('ctx', {}).get('min_length')} characters"
    return "invalid secret value"


def describe_problems(error: ValidationError) -> str:
    problems = [
        f"- {variable_name(issue['loc'])}: {safe_message(issue)}"
        for issue in error.errors(include_input=False, include_url=False)
    ]
    return "\n".join(["Invalid configuration:", *problems])


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        raise ConfigurationError(describe_problems(error)) from None
