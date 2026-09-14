"""Strict structured outputs for the M6 Developer and Reviewer agents."""

from pydantic import Field

from repoagent.ai.models import AIModel, ShortText
from repoagent.domain.repair import PatchPlan, ReviewDecision


class DeveloperOutput(AIModel):
    """One minimal unified-diff proposal grounded in supplied evidence."""

    plan: PatchPlan
    unified_diff: str = Field(min_length=1, max_length=20000)


class ReviewerOutput(AIModel):
    """Review recommendation. Static validator can override approval."""

    decision: ReviewDecision
    rationale: str = Field(min_length=1, max_length=1000)
    concerns: list[ShortText] = Field(default_factory=list, max_length=10)
    recommended_tests: list[ShortText] = Field(default_factory=list, max_length=10)
