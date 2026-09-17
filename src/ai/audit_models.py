"""Strict structured output for the audit Issue Verifier."""

from pydantic import Field, field_validator

from repoagent.ai.models import AIModel, ShortText
from repoagent.domain.audit import VerificationStatus


class VerifierOutput(AIModel):
    """Verifier verdict; only observable evidence, never hidden reasoning."""

    status: VerificationStatus
    reasoning: str = Field(min_length=1, max_length=800)

    @field_validator("status")
    @classmethod
    def _terminal_status_only(cls, value: VerificationStatus) -> VerificationStatus:
        if value == VerificationStatus.PENDING:
            raise ValueError("Verifier must return a terminal verification status")
        return value

    supporting_evidence: list[ShortText] = Field(default_factory=list, max_length=8)
    contradicting_evidence: list[ShortText] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_verification: str = Field(default="", max_length=400)
