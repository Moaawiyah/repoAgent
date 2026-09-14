"""Investigation benchmark computes honest localization metrics."""

from pathlib import Path

from repoagent.adapters.index_store import JsonIndexStore
from repoagent.application.indexing import IndexService
from repoagent.application.investigation import (
    InvestigateRequest,
    InvestigationService,
)
from repoagent.domain.repository import RepositorySpec
from repoagent.evaluation.investigation import (
    InvestigationTask,
    run_investigation_benchmark,
)
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from tests.support.providers import FixtureProvider

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "auth_bug"


def build_service(tmp_path):
    store = JsonIndexStore(tmp_path / "idx")
    embedding = HashingEmbeddingProvider(64)
    IndexService(store, embedding).index(RepositorySpec(source=str(FIXTURE)))
    return InvestigationService(store, embedding, FixtureProvider())


def test_benchmark_reports_measured_values(tmp_path):
    service = build_service(tmp_path)
    tasks = [
        InvestigationTask(
            name="uppercase-email-login",
            repository=str(FIXTURE),
            issue="Users with uppercase email addresses cannot log in",
            expected_files=["app/users/repository.py", "app/auth/service.py"],
            expected_symbols=[
                "app.users.repository.UserRepository.find_by_email",
                "app.auth.service.AuthService.login",
            ],
            expected_root_cause_file="app/users/repository.py",
            expected_root_cause_symbol=(
                "app.users.repository.UserRepository.find_by_email"
            ),
        )
    ]
    outcome = run_investigation_benchmark(
        lambda task: service.investigate(
            InvestigateRequest(
                repository=task.repository, issue=task.issue, max_iterations=2
            )
        ),
        tasks,
    )
    assert outcome.tasks == 1
    assert 0.0 <= outcome.avg_file_recall <= 1.0
    assert 0.0 <= outcome.avg_symbol_recall <= 1.0
    assert outcome.avg_iterations >= 1
    assert outcome.outcomes[0].termination_reason in {
        "confident_root_cause",
        "insufficient_evidence",
        "max_iterations",
    }
    print(
        f"\nbenchmark: file_recall={outcome.avg_file_recall:.2f} "
        f"symbol_recall={outcome.avg_symbol_recall:.2f} "
        f"root_cause={outcome.root_cause_accuracy:.2f} "
        f"iterations={outcome.avg_iterations:.1f}"
    )


def test_localization_requires_precise_symbol(tmp_path):
    from repoagent.domain.investigation import (
        InvestigationReport,
        Issue,
        RootCauseHypothesis,
    )

    task = InvestigationTask(
        name="t",
        repository="/r",
        issue="i",
        expected_files=["users/repository.py"],
        expected_symbols=["r.UserRepository.find_by_email"],
        expected_root_cause_file="users/repository.py",
        expected_root_cause_symbol="r.UserRepository.find_by_email",
    )
    vague = InvestigationReport(
        task_id="t",
        repository="/r",
        issue=Issue(description="i"),
        issue_summary="i",
        hypotheses=[
            RootCauseHypothesis(statement="authentication system", confidence=0.9)
        ],
        primary_hypothesis_id=None,
        confidence=0.9,
        relevant_files=["auth/controller.py"],
    )
    from repoagent.evaluation.investigation import evaluate_task

    assert evaluate_task(task, vague).root_cause_localized is False
    precise = vague.model_copy(
        update={
            "relevant_files": ["users/repository.py"],
            "hypotheses": [
                RootCauseHypothesis(
                    statement="case-sensitive compare",
                    confidence=0.9,
                    affected_symbols=["r.UserRepository.find_by_email"],
                )
            ],
        }
    )
    precise = precise.model_copy(
        update={"primary_hypothesis_id": precise.hypotheses[0].hypothesis_id}
    )
    assert evaluate_task(task, precise).root_cause_localized is False
