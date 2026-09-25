"""Typed access to workflow state that an earlier node must have set."""

from repoagent.domain.errors import RepoAgentError


def required[T](value: T | None, name: str) -> T:
    """Return ``value``; a missing value means the graph ran out of order."""
    if value is None:
        raise RepoAgentError(f"Workflow state is missing {name}")
    return value
