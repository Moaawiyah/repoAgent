"""JSON-file job store; one record and one result file per job."""

import re
import threading
from pathlib import Path

from pydantic import BaseModel

from repoagent.domain.errors import StorageError, TaskNotFound
from repoagent.domain.jobs import JobRecord

_ID = re.compile(r"^[0-9a-f]{32}$")


class FileJobStore:
    def __init__(self, directory: Path) -> None:
        self._directory, self._lock = directory, threading.Lock()

    def _path(self, job_id: str, suffix: str) -> Path:
        if not _ID.fullmatch(job_id):
            raise TaskNotFound("Job not found")
        return self._directory / f"{job_id}{suffix}"

    def _write(self, path: Path, text: str) -> None:
        try:
            self._directory.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(text)
            temporary.replace(path)
        except OSError:
            raise StorageError("Could not persist job state") from None

    def save(self, record: JobRecord) -> None:
        with self._lock:
            self._write(self._path(record.id, ".json"), record.model_dump_json())

    def get(self, job_id: str) -> JobRecord:
        path = self._path(job_id, ".json")
        try:
            return JobRecord.model_validate_json(path.read_text())
        except FileNotFoundError:
            raise TaskNotFound("Job not found") from None
        except (OSError, ValueError):
            raise StorageError("Job record is unreadable") from None

    def recent(self, limit: int) -> list[JobRecord]:
        if not self._directory.is_dir():
            return []
        records = [
            self.get(path.stem)
            for path in self._directory.glob("*.json")
            if _ID.fullmatch(path.stem)
        ]
        return sorted(records, key=lambda r: r.created_at, reverse=True)[:limit]

    def save_result(self, job_id: str, result: BaseModel) -> None:
        with self._lock:
            self._write(self._path(job_id, ".result.json"), result.model_dump_json())

    def result(self, job_id: str) -> str:
        try:
            return self._path(job_id, ".result.json").read_text()
        except FileNotFoundError:
            raise TaskNotFound("Job result not available") from None
