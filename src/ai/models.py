"""Validated structured outputs for investigation prompts.

LLM output is untrusted input: every model caps list sizes and string
lengths and bounds confidence, and unknown fields are rejected.
"""

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from repoagent.domain.evidence import EvidenceRelevance
from repoagent.domain.issue_analysis import IssueAnalysis

__all__ = ["IssueAnalysis"]

ShortText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class AIModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class SearchPlan(AIModel):
    """Focused repository queries; bounded to avoid query explosion."""

    queries: list[ShortText] = Field(min_length=1, max_length=6)


class AssessedEvidence(AIModel):
    """Relevance verdict for one evidence item."""

    evidence_id: str = Field(max_length=64)
    relevance: EvidenceRelevance
    reason: str = Field(default="", max_length=300)


class EvidenceAssessment(AIModel):
    """What the evidence proves and what is still missing."""

    assessments: list[AssessedEvidence] = Field(default_factory=list, max_length=30)
    unknowns: list[ShortText] = Field(default_factory=list, max_length=6)
    next_queries: list[ShortText] = Field(default_factory=list, max_length=4)
    enough_evidence: bool = False


class HypothesisDraft(AIModel):
    """One proposed root cause referencing evidence identifiers."""

    statement: str = Field(max_length=800)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    supporting_evidence_ids: list[ShortText] = Field(
        default_factory=list, max_length=30
    )
    contradicting_evidence_ids: list[ShortText] = Field(
        default_factory=list, max_length=30
    )
    affected_symbols: list[ShortText] = Field(default_factory=list, max_length=8)
    open_questions: list[ShortText] = Field(default_factory=list, max_length=6)


class HypothesisSet(AIModel):
    """Multiple plausible hypotheses; never collapse prematurely."""

    hypotheses: list[HypothesisDraft] = Field(default_factory=list, max_length=4)


class EvaluationVerdict(StrEnum):
    """Outcome of challenging one hypothesis."""

    STRENGTHENED = "strengthened"
    WEAKENED = "weakened"
    UNCONFIRMED = "unconfirmed"


class HypothesisEvaluation(AIModel):
    """Challenge result for one hypothesis."""

    hypothesis_id: str = Field(max_length=64)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    verdict: EvaluationVerdict = EvaluationVerdict.UNCONFIRMED
    notes: str = Field(default="", max_length=400)


class InvestigationDecision(AIModel):
    """Post-evaluation routing decision with bounded confidence."""

    evaluations: list[HypothesisEvaluation] = Field(default_factory=list, max_length=4)
    primary_hypothesis_id: str | None = None
    enough_confidence: bool = False
    next_queries: list[ShortText] = Field(default_factory=list, max_length=4)
