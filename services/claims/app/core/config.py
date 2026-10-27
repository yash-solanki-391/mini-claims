from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.

    In a microservices architecture, these are provided by:
    - Local: .env file at the project root or environment variables.
    - Prod: Kubernetes ConfigMaps/Secrets or a Secret Manager (AWS/Azure/Vault).
    """

    # APP_ENV: 'local', 'test', or 'prod'
    APP_ENV: Literal["local", "test", "prod"]

    # Required in prod, but we provide a default for local dev to prevent startup crashes
    DATABASE_URL: str

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

    # HS256 key for the local/test-only demo token (see app/core/demo_auth.py). Optional so prod never needs it;
    # SecretStr keeps it out of reprs and logs.
    DEMO_JWT_SECRET: SecretStr | None = None

    # Configures pydantic-settings to read from .env if present.
    # We use extra="ignore" so that a single root .env with variables
    # for ALL microservices doesn't cause validation errors in this specific service.
    model_config = SettingsConfigDict(env_file="services/claims/.env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """
    Cached getter for application settings.
    """
    return Settings()


settings = get_settings()
