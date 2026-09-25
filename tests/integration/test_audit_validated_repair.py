"""`audit --repair --execute`: verified finding -> unchanged M7 validated repair."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from repoagent import RepoAgent, Settings
from repoagent.ai.provider import CompletionResult
from repoagent.cli.main import app
from repoagent.domain.errors import AuditError
from repoagent.domain.repair_execution import ExecutionStatus
from tests.support.execution_provider import ExecutionProvider
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

AUTH = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
RED = execution(pytest_result(passed=2, failed=["tests/test_login.py::test_upper"]))
GREEN = execution(pytest_result(passed=3))
PLANTED = "\n\ndef remember(item, seen=[]):\n    seen.append(item)\n    return seen\n"


class AuditRepairProvider(ExecutionProvider):
    """Verifies every audit candidate, then plays the M5-M7 repair script."""

    def __init__(self, verdict="verified"):
        super().__init__()
        self._verdict = verdict

    def complete(self, request):
        if request.prompt_name == "audit_verification":
            payload = {"status": self._verdict, "reasoning": "Shared default list."}
            text = json.dumps({**payload, "confidence": 0.8})
            return CompletionResult(text=text, model=self.name)
        return super().complete(request)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(AUTH, root)
    with (root / "app/users/repository.py").open("a") as handle:
        handle.write(PLANTED)
    return root


def digest(root: Path) -> str:
    files = sorted(p for p in root.rglob("*") if p.is_file())
    content = b"".join(
        p.relative_to(root).as_posix().encode() + p.read_bytes() for p in files
    )
    return hashlib.sha256(content).hexdigest()


@pytest.fixture
def sandbox(monkeypatch):
    fake = FakeSandboxRunner(attempts=[RED, GREEN])
    monkeypatch.setattr(
        "repoagent.sdk.validated_repair.DockerSandboxRunner",
        lambda image, workspace_dir=None: fake,
    )
    return fake


def client(tmp_path):
    return RepoAgent(settings=Settings(data_dir=tmp_path / "data"))


def test_verified_finding_runs_full_validated_repair(tmp_path, repo, sandbox):
    before = digest(repo)
    report = client(tmp_path).audit(
        repo, limit=5, repair=True, execute=True, provider=AuditRepairProvider()
    )
    validated = report.validated_repair
    assert validated is not None and validated.status is ExecutionStatus.VALIDATED
    assert report.metrics.repair_status == "validated" and report.repair is None
    chosen = next(c for c in report.candidates if c.id == report.repair_candidate_id)
    assert chosen.status == "verified" and "remember" in (chosen.symbol or chosen.title)
    assert validated.investigation.issue.title == chosen.title
    assert validated.attempts and validated.metrics.llm_calls > 0
    assert digest(repo) == before


def test_execute_without_verified_finding_skips_repair(tmp_path, repo, sandbox):
    report = client(tmp_path).audit(
        repo, repair=True, execute=True, provider=AuditRepairProvider("rejected")
    )
    assert report.validated_repair is None
    assert report.metrics.repair_status == "no_verified_candidate"
    assert sandbox.overlays == []


def test_execute_requires_repair(tmp_path, repo):
    with pytest.raises(AuditError):
        client(tmp_path).audit(repo, execute=True, provider=AuditRepairProvider())


def test_cli_repair_execute_renders_and_validates_flags(
    tmp_path, repo, sandbox, monkeypatch
):
    monkeypatch.setattr(
        "repoagent.sdk.audit.llm_provider_from_settings",
        lambda settings: AuditRepairProvider(),
    )
    base = ["--data-dir", str(tmp_path / "data"), "audit", str(repo)]
    result = CliRunner().invoke(
        app, [*base, "--repair", "--execute", "--max-attempts", "2"]
    )
    assert result.exit_code == 0, result.output
    assert "Validated Repair (finding" in result.output
    for flags in (
        ["--execute"],
        ["--max-attempts", "2"],
        ["--repair", "--timeout", "5"],
    ):
        assert CliRunner().invoke(app, [*base, *flags]).exit_code == 2
