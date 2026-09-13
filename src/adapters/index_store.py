"""File-based JSON persistence for retrieval index snapshots."""

import json
import logging
import os
from pathlib import Path

from repoagent.domain.errors import IndexNotFound, StorageError
from repoagent.retrieval.models import IndexSnapshot


class JsonIndexStore:
    """Stores one JSON document per repository index under a base dir.

    Writes are atomic (temporary file plus replace). Loading a missing or
    unreadable index raises typed errors at the public boundary instead of
    leaking filesystem details.
    """

    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir

    def _path(self, repo_id: str) -> Path:
        return self._base / f"{repo_id}.json"

    def exists(self, repo_id: str) -> bool:
        return self._path(repo_id).is_file()

    def save(self, snapshot: IndexSnapshot) -> None:
        path = self._path(snapshot.repo_id)
        try:
            self._base.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(snapshot.model_dump_json(), encoding="utf-8")
            os.replace(temporary, path)
        except OSError:
            logging.getLogger(__name__).warning(
                "Index save failed", extra={"event": "index_save_failed"}
            )
            raise StorageError("Index persistence failed") from None

    def load(self, repo_id: str) -> IndexSnapshot:
        try:
            data = json.loads(self._path(repo_id).read_text(encoding="utf-8"))
            return IndexSnapshot.model_validate(data)
        except FileNotFoundError:
            raise IndexNotFound("Repository has not been indexed") from None
        except (OSError, ValueError):
            raise StorageError("Index could not be read") from None
