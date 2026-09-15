"""Challenge/refine routing and semantic checks on model-controlled citations."""

import json
from pathlib import Path

import pytest

from repoagent import RepoAgent, Settings
from repoagent.ai.provider import CompletionResult
from tests.support.providers import FixtureProvider

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"


class ChallengeProvider(FixtureProvider):
    def complete(self, request):
        result = super().complete(request)
        data = json.loads(request.user)["untrusted_data"]
        if request.prompt_name == "investigation_decision" and data["iteration"] == 1:
            payload = json.loads(result.text)
            payload["enough_confidence"] = False
            payload["next_queries"] = ["case insensitive email normalize"]
            payload["evaluations"][0].update(
                verdict="unconfirmed",
                confidence=0.95,
                notes="Need to inspect normalization before lookup.",
            )
            return CompletionResult(text=json.dumps(payload))
        return result


def run(tmp_path, provider):
    client = RepoAgent(settings=Settings(data_dir=tmp_path / "data"))
    client.index(FIXTURE)
    return client.investigate(FIXTURE, "email login", provider=provider)


def test_hypothesis_challenge_causes_new_search(tmp_path):
    provider = ChallengeProvider()
    report = run(tmp_path, provider)
    stages = [r.prompt_name for r in provider.requests]
    first = stages.index("investigation_decision")
    assert "evidence_assessment" in stages[first + 1 :]
    assert report.iterations == 2
    assert report.termination_reason == "confident_root_cause"
    assert any("normalization" in t.rationale for t in report.trace)


@pytest.mark.parametrize(
    "stage",
    [
        "search_plan",
        "evidence_assessment",
        "hypothesis_set",
        "investigation_decision",
    ],
)
def test_malformed_stage_returns_persisted_failure(tmp_path, stage):
    class Malformed(FixtureProvider):
        def complete(self, request):
            if request.prompt_name == stage:
                return CompletionResult(text='{"unexpected":true}')
            return super().complete(request)

    report = run(tmp_path, Malformed())
    assert report.termination_reason == "provider_error"
    assert f"Invalid structured output for {stage}" in report.error
    assert report.confidence <= 0.6
    assert list((tmp_path / "data/investigations").glob("*.json"))


@pytest.mark.parametrize("mutation", ["unsupported_symbol", "uncited", "contradicted"])
def test_confidence_requires_usable_evidence(tmp_path, mutation):
    class Mutated(FixtureProvider):
        def complete(self, request):
            result = super().complete(request)
            if request.prompt_name == "hypothesis_set":
                payload = json.loads(result.text)
                draft = payload["hypotheses"][0]
                if mutation == "unsupported_symbol":
                    draft["affected_symbols"] = ["invented.auth"]
                elif mutation == "uncited":
                    draft["supporting_evidence_ids"] = []
                else:
                    draft["contradicting_evidence_ids"] = draft[
                        "supporting_evidence_ids"
                    ]
                return CompletionResult(text=json.dumps(payload))
            return result

    report = run(tmp_path, Mutated())
    assert report.termination_reason != "confident_root_cause"
    assert report.confidence <= 0.6


def test_investigation_cannot_invoke_commands(tmp_path, monkeypatch):
    import subprocess

    client = RepoAgent(settings=Settings(data_dir=tmp_path / "data"))
    client.index(FIXTURE)

    def forbidden(*args, **kwargs):
        raise AssertionError("M5 must never execute a subprocess")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    report = client.investigate(FIXTURE, "email login", provider=FixtureProvider())
    assert report.primary_hypothesis is not None


def test_last_round_cannot_override_insufficient_assessment(tmp_path):
    client = RepoAgent(settings=Settings(data_dir=tmp_path / "data"))
    client.index(FIXTURE)
    report = client.investigate(
        FIXTURE,
        "email login",
        provider=FixtureProvider(rounds=10),
        max_iterations=1,
    )
    assert report.termination_reason == "max_iterations"
    assert report.confidence <= 0.6


@pytest.mark.parametrize("invalid_only", [False, True])
def test_unknown_evidence_ids_are_discarded_not_trusted(tmp_path, invalid_only):
    class Mistyped(FixtureProvider):
        def complete(self, request):
            result = super().complete(request)
            if request.prompt_name != "evidence_assessment":
                return result
            payload = json.loads(result.text)
            fake = {"evidence_id": "ffffffffffffffff", "relevance": "relevant"}
            kept = [] if invalid_only else payload["assessments"]
            payload["assessments"] = [*kept, fake]
            return CompletionResult(text=json.dumps(payload))

    report = run(tmp_path, Mistyped())
    assert all(e.evidence_id != "ffffffffffffffff" for e in report.evidence)
    if invalid_only:
        assert report.termination_reason == "provider_error"
    else:
        assert report.termination_reason == "confident_root_cause"
        assert any("discarded 1 unknown" in t.rationale for t in report.trace)
