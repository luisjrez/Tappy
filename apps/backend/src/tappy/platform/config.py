from collections.abc import Sequence

from pydantic import Field, SecretStr, ValidationError, ValidationInfo, field_validator
from pydantic_core import ErrorDetails
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "TAPPY_"


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
    public_base_url: str = Field(default="http://127.0.0.1:8000", pattern=r"^https?://[^/?#]+$")
    password_reset_ttl_seconds: int = Field(default=1800, ge=300)
    password_min_length: int = Field(default=12, ge=8, le=128)
    password_max_length: int = Field(default=128, ge=12, le=1024)
    recovery_limit_per_email: int = Field(default=3, ge=1)
    recovery_limit_per_origin: int = Field(default=10, ge=1)
    recovery_window_seconds: int = Field(default=3600, ge=60)
    smtp_host: str = "127.0.0.1"
    smtp_port: int = Field(default=1025, ge=1, le=65535)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    mail_from: str = "Tappy <no-reply@tappy.example>"
    delivery_max_attempts: int = Field(default=5, ge=1)

    @field_validator("password_max_length")
    @classmethod
    def password_bounds_are_consistent(cls, maximum: int, info: ValidationInfo) -> int:
        minimum = info.data.get("password_min_length")
        if isinstance(minimum, int) and minimum > maximum:
            raise ValueError("must not be lower than TAPPY_PASSWORD_MIN_LENGTH")
        return maximum


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
