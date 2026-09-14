"""Validated inputs and bounded read-only tool results."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from repoagent.domain.errors import InvestigationError


class ToolModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SearchCodeInput(ToolModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def clean(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must not be empty")
        return value.strip()


class FileInput(ToolModel):
    path: str = Field(min_length=1, max_length=1000)
    start_line: int = Field(default=1, ge=1)
    end_line: int | None = Field(default=None, ge=1)

    @field_validator("path")
    @classmethod
    def safe(cls, value: str) -> str:
        from pathlib import PurePosixPath

        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise InvestigationError("Unsafe file path rejected")
        return value


class FileInspection(ToolModel):
    path: str
    start_line: int
    end_line: int
    content: str
    exists: bool = True


class NeighborReport(ToolModel):
    node_id: str
    node_type: str
    file_path: str
    relation: str
    resolved: bool
