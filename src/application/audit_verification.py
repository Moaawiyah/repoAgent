"""Runs the LLM Issue Verifier over every enriched candidate.

A malformed/invalid structured response for one candidate never aborts the
run: that candidate is reported UNCERTAIN with an observable reason rather
than silently dropped or upgraded to VERIFIED.
"""

import time

from repoagent.agent.audit_verifier import IssueVerifier
from repoagent.ai.provider import LLMProvider
from repoagent.domain.audit import CandidateIssue, VerificationStatus, VerifierFinding
from repoagent.domain.audit_report import AuditMetrics
from repoagent.domain.errors import LLMError, LLMOutputError

_TERMINAL = (
    VerificationStatus.VERIFIED,
    VerificationStatus.UNCERTAIN,
    VerificationStatus.REJECTED,
)


def _unverifiable(candidate: CandidateIssue, reason: str) -> CandidateIssue:
    return candidate.model_copy(
        update={
            "status": VerificationStatus.UNCERTAIN,
            "verification": VerifierFinding(
                status=VerificationStatus.UNCERTAIN, reasoning=reason, confidence=0.0
            ),
        }
    )


def verify_candidates(
    provider: LLMProvider, candidates: list[CandidateIssue]
) -> tuple[list[CandidateIssue], AuditMetrics]:
    if not candidates:
        return candidates, AuditMetrics()
    verifier = IssueVerifier(provider)
    results, input_tokens, output_tokens = [], 0, 0
    started = time.monotonic()
    for candidate in candidates:
        try:
            verified, result = verifier.verify(candidate)
        except (LLMError, LLMOutputError):
            results.append(_unverifiable(candidate, "Verifier output was invalid."))
            continue
        results.append(verified)
        input_tokens += result.usage.input_tokens
        output_tokens += result.usage.output_tokens
    duration = time.monotonic() - started
    counts = {
        status: sum(1 for c in results if c.status == status) for status in _TERMINAL
    }
    metrics = AuditMetrics(
        verified=counts[VerificationStatus.VERIFIED],
        uncertain=counts[VerificationStatus.UNCERTAIN],
        rejected=counts[VerificationStatus.REJECTED],
        verification_llm_calls=len(candidates),
        verification_input_tokens=input_tokens,
        verification_output_tokens=output_tokens,
        verification_duration_seconds=duration,
    )
    return results, metrics
