"""Workflow test doubles: offline GitHub loader and a verifier-aware provider."""

import json
from pathlib import Path

from repoagent import RepoAgent, Settings
from repoagent.ai.provider import CompletionResult
from repoagent.domain.github import RepositoryHandle, parse_github_url
from tests.support.execution_provider import ExecutionProvider
from tests.support.sandbox import FakeSandboxRunner, execution, pytest_result

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
AUTH_URL = "https://github.com/acme/auth_bug"
AUDIT_URL = "https://github.com/acme/audit_repo"
COMMIT = "a" * 40
_VERDICTS = {
    "exception_handling": ("verified", 0.9),
    "circular_dependency": ("verified", 0.85),
    "todo_marker": ("rejected", 0.7),
}


class FixtureLoader:
    """Maps GitHub URLs to local fixtures instead of fetching (offline tests)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, source: str) -> RepositoryHandle:
        self.calls.append(source)
        repository = parse_github_url(source)
        path = FIXTURES / repository.name
        return RepositoryHandle(
            source=repository.url, name=repository.slug, path=str(path), commit=COMMIT
        )


class WorkflowProvider(ExecutionProvider):
    """ExecutionProvider plus deterministic Issue Verifier decisions."""

    def complete(self, request):
        if request.prompt_name != "audit_verification":
            return super().complete(request)
        self.requests.append(request)
        candidate = json.loads(request.user)["untrusted_data"]["candidate"]
        status, confidence = _VERDICTS.get(candidate["category"], ("uncertain", 0.4))
        result = {
            "status": status,
            "reasoning": f"Fixture verdict for {candidate['category']}.",
            "supporting_evidence": [candidate["file"]],
            "confidence": confidence,
        }
        return CompletionResult(text=json.dumps(result), model=self.name)


def passing_sandbox() -> FakeSandboxRunner:
    return FakeSandboxRunner(attempts=[execution(pytest_result(passed=3))])


def workflow_client(tmp_path, runner=None, **settings) -> RepoAgent:
    return RepoAgent(
        settings=Settings(data_dir=tmp_path / "data", **settings),
        sandbox_runner=runner or passing_sandbox(),
    )
