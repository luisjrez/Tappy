from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_PREFIX = "TAPPY_"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, frozen=True)

    environment: str = Field(min_length=1)
    secret_key: SecretStr = Field(min_length=32)
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)


class ConfigurationError(Exception):
    pass


def describe_problems(error: ValidationError) -> str:
    problems = [
        f"{ENV_PREFIX}{'_'.join(str(part) for part in issue['loc']).upper()}: {issue['msg']}"
        for issue in error.errors(include_input=False, include_url=False)
    ]
    return "Invalid configuration:\n" + "\n".join(f"- {problem}" for problem in problems)


def load_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as error:
        raise ConfigurationError(describe_problems(error)) from None
