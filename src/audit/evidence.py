"""Evidence enrichment for candidates via the existing hybrid/graph RAG.

Reuses ``RepositoryToolkit.search_code`` as-is (same bounded ``EvidenceItem``
provenance the investigator uses) — a few ranked chunks per candidate, never
whole files or the whole repository.
"""

from repoagent.domain.audit import CandidateIssue
from repoagent.tools.repository import RepositoryToolkit

EVIDENCE_TOP_K = 3


def enrich(
    candidates: list[CandidateIssue], toolkit: RepositoryToolkit
) -> list[CandidateIssue]:
    """Attach focused, bounded evidence to each candidate."""
    return [
        candidate.model_copy(
            update={"evidence": toolkit.search_code(_query(candidate), EVIDENCE_TOP_K)}
        )
        for candidate in candidates
    ]


def _query(candidate: CandidateIssue) -> str:
    focus = candidate.symbol or candidate.file
    return f"{candidate.category.value} {focus} {candidate.title}"
