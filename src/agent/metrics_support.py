"""Measured usage and patch-size fields shared by repair report builders."""

from repoagent.ai.counting import CountingProvider


def usage_fields(provider: CountingProvider) -> dict:
    """Provider-reported token usage plus prompt-size and per-stage call counts."""
    return {
        "llm_calls": provider.calls,
        "input_tokens": provider.total("input_tokens"),
        "output_tokens": provider.total("output_tokens"),
        "prompt_chars": provider.total("prompt_chars"),
        "stage_calls": {name: stage.calls for name, stage in provider.stages.items()},
    }


def diff_stats(unified_diff: str | None) -> tuple[int, int]:
    """Return (lines added, lines removed) excluding file headers."""
    added = removed = 0
    for line in (unified_diff or "").splitlines():
        if line.startswith(("+++", "---")):
            continue
        added += line.startswith("+")
        removed += line.startswith("-")
    return added, removed
