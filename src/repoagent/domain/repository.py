"""Inert repository input validation; never execute target content."""

import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


class RepositorySpec(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: str
    commit: str | None = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, value: str, info: ValidationInfo) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Repository source is required")
        if "://" in value or value.startswith("git@"):
            url = urlsplit(value)
            if (
                url.scheme != "https"
                or url.netloc != "github.com"
                or url.query
                or url.fragment
                or not re.fullmatch(r"/[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+/?", url.path)
                or url.path.rstrip("/").split("/")[-1] in {".", "..", ".git"}
            ):
                raise ValueError("Use an HTTPS github.com owner/repository URL")
            return value.rstrip("/")
        path = Path(value).expanduser().resolve()
        if not (info.context or {}).get("persisted") and not path.is_dir():
            raise ValueError("Local repository source must be an existing directory")
        return str(path)

    @field_validator("commit")
    @classmethod
    def validate_commit(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("Commit reference must be nonempty and contain no NUL")
        return value
