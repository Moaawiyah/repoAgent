"""Configured graph policies reach the agent's retrieval, not only search."""

from pathlib import Path

from repoagent import RepoAgent, Settings
from repoagent.application import investigation
from tests.support.providers import FixtureProvider

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"


def test_settings_policy_reaches_the_investigator(tmp_path, monkeypatch):
    seen = []
    original = investigation.SearchService

    def spy(store, embedding, **kwargs):
        seen.append(kwargs.get("graph_policy"))
        return original(store, embedding, **kwargs)

    monkeypatch.setattr(investigation, "SearchService", spy)
    settings = Settings(data_dir=tmp_path / "d", graph_policy="focused")
    agent = RepoAgent(settings=settings)
    agent.index(FIXTURE)
    agent.investigate(
        FIXTURE, "Uppercase emails cannot log in", provider=FixtureProvider()
    )
    assert seen and seen[0].name == "focused"
