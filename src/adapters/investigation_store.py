"""Durable JSON reports containing observable trace, never model reasoning."""

from pathlib import Path
from uuid import UUID

from repoagent.adapters.json_report import write_report
from repoagent.domain.errors import StorageError
from repoagent.domain.investigation import InvestigationReport


class InvestigationStore:
    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def save(self, report: InvestigationReport) -> Path:
        return write_report(
            self._directory,
            report.task_id,
            report.repository,
            report.model_dump_json(indent=2),
        )

    def get(self, task_id: str) -> InvestigationReport:
        identifier = str(UUID(task_id))
        try:
            payload = (self._directory / f"{identifier}.json").read_text()
            return InvestigationReport.model_validate_json(payload)
        except (OSError, ValueError):
            raise StorageError("Investigation report is missing or invalid") from None
