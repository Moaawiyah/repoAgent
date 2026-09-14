"""Real LangGraph routing with real retrieval and test-only model responses."""

from pathlib import Path

import pytest

from repoagent.adapters.index_store import JsonIndexStore
from repoagent.application.indexing import IndexService
from repoagent.application.investigation import InvestigateRequest, InvestigationService
from repoagent.domain.investigation import InvestigationLimits
from repoagent.domain.repository import RepositorySpec
from repoagent.retrieval.embeddings import HashingEmbeddingProvider
from tests.support.providers import FixtureProvider
from tests.support.scripted import ScriptedLLMProvider

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
ISSUE = "Users with uppercase emails cannot log in"


@pytest.fixture
def run_agent(tmp_path):
    def run(provider, *, limits=None, repository=FIXTURE):
        store = JsonIndexStore(tmp_path / "indexes")
        embedding = HashingEmbeddingProvider(64)
        IndexService(store, embedding).index(RepositorySpec(source=str(repository)))
        return InvestigationService(store, embedding, provider).investigate(
            InvestigateRequest(repository=str(repository), issue=ISSUE), limits
        )

    return run


def test_immediate_evidence(run_agent):
    report = run_agent(FixtureProvider())
    assert report.termination_reason == "confident_root_cause"
    assert report.iterations == report.tool_calls == 1
    assert report.primary_hypothesis.supporting_evidence
    assert report.confidence == 0.8
    assert report.issue_analysis and report.queries
    assert report.graph_paths


def test_refinement_is_a_second_retrieval(run_agent):
    report = run_agent(FixtureProvider(rounds=2))
    assert report.iterations == 2
    assert report.tool_calls == 2
    assert len(set(report.queries)) == 2
    assert any(e.action == "query_refined" for e in report.trace)
    assert report.termination_reason == "confident_root_cause"


def test_max_iterations_reduces_confidence(run_agent):
    report = run_agent(
        FixtureProvider(rounds=10, weak=True),
        limits=InvestigationLimits(max_iterations=2),
    )
    assert report.termination_reason == "max_iterations"
    assert report.iterations == 2 and report.confidence <= 0.6


def test_multiple_hypotheses_are_evaluated(run_agent):
    report = run_agent(FixtureProvider(multiple=True))
    assert len(report.hypotheses) == 2
    assert all(h.status == "evaluated" for h in report.hypotheses)
    assert report.primary_hypothesis.confidence == max(
        h.confidence for h in report.hypotheses
    )


def test_empty_repository_returns_insufficient_evidence(run_agent, tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    report = run_agent(FixtureProvider(), repository=root)
    assert report.termination_reason == "insufficient_evidence"
    assert not report.evidence and not report.hypotheses


def test_malformed_output_is_not_an_invalid_issue(run_agent):
    report = run_agent(ScriptedLLMProvider(["not json"]))
    assert report.termination_reason == "provider_error"
    assert report.error and report.usage.llm_calls == 1


@pytest.mark.parametrize(
    "budget,reason",
    [
        ({"max_queries": 1}, "max_queries"),
        ({"max_tool_calls": 1}, "max_tool_calls"),
        ({"max_evidence": 1}, "max_evidence"),
    ],
)
def test_hard_budgets(run_agent, budget, reason):
    report = run_agent(
        FixtureProvider(rounds=10, weak=True), limits=InvestigationLimits(**budget)
    )
    assert report.termination_reason == reason
    assert report.tool_calls == 1
    assert report.confidence <= 0.6
