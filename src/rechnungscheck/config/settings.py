"""Application settings, read from environment variables prefixed ``RC_``."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    LOCAL = "local"
    CI = "ci"
    DEV = "dev"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RC_", env_file=".env", extra="ignore", frozen=True)

    environment: Environment = Environment.LOCAL
    tenants_dir: Path = Path("tenants")
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
