"""Framework-independent, bounded issue understanding."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class IssueAnalysis(BaseModel):
    """Understanding of the issue before any retrieval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    symptoms: list[ShortText] = Field(default_factory=list, max_length=6)
    expected_behavior: str = Field(default="", max_length=500)
    observed_behavior: str = Field(default="", max_length=500)
    errors: list[ShortText] = Field(default_factory=list, max_length=6)
    likely_subsystem: str = Field(default="", max_length=200)
    identifiers: list[ShortText] = Field(default_factory=list, max_length=10)
    concepts: list[ShortText] = Field(default_factory=list, max_length=10)
    initial_questions: list[ShortText] = Field(default_factory=list, max_length=6)
