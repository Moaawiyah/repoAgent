"""Explicit environment configuration without automatic dotenv discovery."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REPOAGENT_", extra="ignore")
    data_dir: Path = Path.home() / ".repoagent"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    max_retries: int = Field(default=3, ge=0, le=20)
    context_budget: int = Field(default=16000, gt=0)
    execution_timeout: int = Field(default=300, gt=0)
    embedding_provider: Literal["hashing"] = "hashing"
    embedding_dimension: int = Field(default=256, gt=0, le=4096)

    @field_validator("data_dir")
    @classmethod
    def expand_data_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()
