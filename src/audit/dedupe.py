"""Deduplicates overlapping candidate findings before verification.

Two candidates are the same finding when they share a file and category and
their line ranges overlap — regardless of which detector produced them. The
higher-confidence candidate survives; ordering is deterministic (sorted by
file, category, start line) so repeated runs collapse the same way.
"""

from repoagent.domain.audit import CandidateIssue


def _overlaps(a: CandidateIssue, b: CandidateIssue) -> bool:
    return a.start_line <= b.end_line and b.start_line <= a.end_line


def deduplicate(candidates: list[CandidateIssue]) -> tuple[list[CandidateIssue], int]:
    """Return (deduplicated candidates, count removed)."""
    ordered = sorted(
        candidates,
        key=lambda c: (c.file, c.category.value, c.start_line, -c.confidence),
    )
    kept: list[CandidateIssue] = []
    removed = 0
    for candidate in ordered:
        merged = False
        for index, existing in enumerate(kept):
            if (
                existing.file == candidate.file
                and existing.category == candidate.category
                and _overlaps(existing, candidate)
            ):
                if candidate.confidence > existing.confidence:
                    kept[index] = candidate
                removed += 1
                merged = True
                break
        if not merged:
            kept.append(candidate)
    return kept, removed
