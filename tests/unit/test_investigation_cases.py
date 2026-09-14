"""Controlled-case runner: offline scores describe test routing, not AI accuracy."""

from pathlib import Path

from pydantic import TypeAdapter

from repoagent import RepoAgent, Settings
from repoagent.evaluation.investigation import (
    InvestigationTask,
    run_investigation_benchmark,
)
from tests.support.providers import FixtureProvider


def test_controlled_case_runner(tmp_path):
    path = Path(__file__).resolve().parents[1] / "fixtures/investigation_cases.json"
    tasks = TypeAdapter(list[InvestigationTask]).validate_json(path.read_text())
    client = RepoAgent(settings=Settings(data_dir=tmp_path))

    def investigate(task):
        client.index(task.repository)
        return client.investigate(
            task.repository,
            task.issue,
            provider=FixtureProvider(rounds=2),
        )

    outcome = run_investigation_benchmark(investigate, tasks)
    assert outcome.tasks == 2
    assert outcome.avg_iterations == 2
    assert outcome.avg_retrieval_calls == 2
    assert all(0 <= o.file_recall <= 1 for o in outcome.outcomes)
    print("OFFLINE SCRIPTED ROUTING SCORES:", outcome.model_dump_json())


def test_benchmark_command_uses_public_sdk(tmp_path, monkeypatch, capsys):
    import sys

    from scripts.benchmark_investigation import main

    monkeypatch.setattr(
        "repoagent.sdk.investigation.llm_provider_from_settings",
        lambda settings: FixtureProvider(),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmark_investigation.py",
            "tests/fixtures/investigation_cases.json",
            "--data-dir",
            str(tmp_path),
        ],
    )
    main()
    import json

    assert json.loads(capsys.readouterr().out)["tasks"] == 2
