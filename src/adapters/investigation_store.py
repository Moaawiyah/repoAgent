"""Durable JSON reports containing observable trace, never model reasoning."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from repoagent.domain.errors import StorageError
from repoagent.domain.investigation import InvestigationReport


class InvestigationStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, report: InvestigationReport) -> Path:
        identifier = str(UUID(report.task_id))
        directory = self._directory.expanduser().resolve()
        if directory.is_relative_to(Path(report.repository).resolve()):
            raise StorageError("Investigation storage must be outside the repository")
        temporary = None
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"{identifier}.json"
            with NamedTemporaryFile(mode="w", dir=directory, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(report.model_dump_json(indent=2))
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(target)
            return target
        except OSError:
            raise StorageError("Could not persist investigation report") from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def get(self, task_id: str) -> InvestigationReport:
        identifier = str(UUID(task_id))
        try:
            payload = (self._directory / f"{identifier}.json").read_text()
            return InvestigationReport.model_validate_json(payload)
        except (OSError, ValueError):
            raise StorageError("Investigation report is missing or invalid") from None
