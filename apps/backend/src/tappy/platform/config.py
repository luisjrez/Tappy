import base64
import binascii
from collections.abc import Sequence
from typing import Literal, Self

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_core import ErrorDetails
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "TAPPY_"
PROVIDER_MAX_AMOUNT_CENTS = 100_000_000
PEY_KEY_REQUIRED = "TAPPY_PEY_API_KEY is required when TAPPY_PAYMENT_PROVIDER is pey"
PROVIDER_TIMEOUT_PHASES = 4
MAX_QUERY_PAGES = 10
STANDARD_WEBHOOKS_PREFIX = "whsec_"
WEBHOOK_KEY_MIN_BYTES = 24
PEY_BASE_URL = r"^(https://|http://(127\.0\.0\.1|localhost)(:\d+)?(/|$))"


def standard_webhook_key(secret: str) -> bytes:
    if not secret.startswith(STANDARD_WEBHOOKS_PREFIX):
        raise binascii.Error("missing whsec_ prefix")
    return base64.b64decode(secret.removeprefix(STANDARD_WEBHOOKS_PREFIX), validate=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, frozen=True)

    environment: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,31}$")
    secret_key: SecretStr = Field(min_length=32)
    database_url: SecretStr = Field(min_length=1)
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    access_token_ttl_seconds: int = Field(default=900, ge=60)
    session_max_lifetime_seconds: int = Field(default=30 * 24 * 3600, ge=3600)
    admin_secure_cookies: bool = True
    payment_provider: Literal["simulated", "pey"] = "simulated"
    pey_base_url: str = Field(default="https://api.pey.mx", pattern=PEY_BASE_URL)
    pey_api_key: SecretStr | None = Field(default=None, min_length=16)
    pey_timeout_seconds: float = Field(default=10, gt=0, le=60)
    attempt_creation_timeout_seconds: int = Field(default=60, ge=1)
    job_lease_seconds: int = Field(default=600, ge=1)
    job_batch_size: int = Field(default=20, ge=1, le=100)
    job_max_tries: int = Field(default=8, ge=1, le=50)
    job_backoff_seconds: int = Field(default=60, ge=1)
    job_backoff_max_seconds: int = Field(default=3600, ge=1, le=24 * 3600)
    pey_webhook_secret: SecretStr | None = None
    webhook_tolerance_seconds: int = Field(default=300, ge=1, le=3600)
    webhook_max_body_bytes: int = Field(default=256 * 1024, ge=1024, le=1024 * 1024)
    sale_max_amount_cents: int = Field(
        default=PROVIDER_MAX_AMOUNT_CENTS, ge=1, le=PROVIDER_MAX_AMOUNT_CENTS
    )

    @field_validator("pey_webhook_secret")
    @classmethod
    def webhook_secret_format(cls, secret: SecretStr | None) -> SecretStr | None:
        if secret is None:
            return None
        try:
            key = standard_webhook_key(secret.get_secret_value())
        except binascii.Error:
            key = b""
        if len(key) < WEBHOOK_KEY_MIN_BYTES:
            raise ValueError("must be a Standard Webhooks secret (whsec_ followed by base64)")
        return secret

    @model_validator(mode="after")
    def pey_needs_a_key(self) -> Self:
        if self.payment_provider == "pey" and self.pey_api_key is None:
            raise ValueError(PEY_KEY_REQUIRED)
        return self

    @model_validator(mode="after")
    def creation_outlasts_provider_calls(self) -> Self:
        if (
            self.attempt_creation_timeout_seconds
            <= PROVIDER_TIMEOUT_PHASES * self.pey_timeout_seconds
        ):
            raise ValueError(
                "TAPPY_ATTEMPT_CREATION_TIMEOUT_SECONDS must exceed "
                f"{PROVIDER_TIMEOUT_PHASES} times TAPPY_PEY_TIMEOUT_SECONDS"
            )
        return self

    @model_validator(mode="after")
    def lease_outlasts_a_query(self) -> Self:
        query_seconds = MAX_QUERY_PAGES * PROVIDER_TIMEOUT_PHASES * self.pey_timeout_seconds
        if self.payment_provider == "pey" and self.job_lease_seconds <= query_seconds:
            raise ValueError(
                "TAPPY_JOB_LEASE_SECONDS must exceed "
                f"{MAX_QUERY_PAGES * PROVIDER_TIMEOUT_PHASES} times TAPPY_PEY_TIMEOUT_SECONDS"
            )
        return self

    @model_validator(mode="after")
    def backoff_is_bounded(self) -> Self:
        if self.job_backoff_max_seconds < self.job_backoff_seconds:
            raise ValueError(
                "TAPPY_JOB_BACKOFF_MAX_SECONDS must be at least TAPPY_JOB_BACKOFF_SECONDS"
            )
        return self


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
