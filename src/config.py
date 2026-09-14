"""Explicit environment configuration without automatic dotenv discovery."""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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
    llm_provider: Literal["none", "groq", "openai"] = "none"
    llm_model: str = "openai/gpt-oss-20b"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    investigation_max_iterations: int = Field(default=3, ge=1, le=10)

    investigation_max_queries: int = Field(default=8, ge=1, le=20)
    investigation_max_evidence: int = Field(default=12, ge=1, le=30)
    investigation_max_tool_calls: int = Field(default=30, ge=1, le=100)
    investigation_context_chars: int = Field(default=12000, ge=1000, le=16000)
    llm_timeout: int = Field(default=60, ge=1, le=300)
    llm_max_output_tokens: int = Field(default=2000, ge=128, le=8000)
    repair_max_revisions: int = Field(default=2, ge=0, le=5)

    @field_validator("data_dir")
    @classmethod
    def expand_data_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()
