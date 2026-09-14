"""Persistence contract for retrieval indexes."""

from typing import Protocol

from repoagent.retrieval.persistence import IndexSnapshot


class IndexStore(Protocol):
    """Durable storage for repository index snapshots."""

    def save(self, snapshot: IndexSnapshot) -> None: ...

    def load(self, repo_id: str) -> IndexSnapshot: ...

    def exists(self, repo_id: str) -> bool: ...
