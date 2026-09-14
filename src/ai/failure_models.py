"""Strict structured output for the M7 Failure Analyzer."""

from pydantic import Field

from repoagent.ai.models import AIModel, ShortText
from repoagent.domain.repair_execution import FailureCategory, NextAction


class FailureAnalyzerOutput(AIModel):
    """Concise diagnosis of a failed sandbox validation; no reasoning trace."""

    category: FailureCategory
    likely_reason: str = Field(min_length=1, max_length=800)
    affected_file: str | None = Field(default=None, max_length=300)
    affected_symbol: str | None = Field(default=None, max_length=300)
    patch_caused_failure: bool
    root_cause_uncertain: bool = False
    next_action: NextAction
    evidence_needed: list[ShortText] = Field(default_factory=list, max_length=6)
