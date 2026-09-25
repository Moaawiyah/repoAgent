"""scripts/typecheck.py runs mypy against a real ``repoagent`` package root."""

import subprocess
from pathlib import Path

from scripts import typecheck


def test_typecheck_exposes_src_as_repoagent(monkeypatch):
    seen = {}

    def fake_run(command, cwd, env, check):
        root = Path(env["MYPYPATH"])
        seen["linked"] = (root / "repoagent").resolve() == typecheck.ROOT / "src"
        seen["command"] = command
        return subprocess.CompletedProcess(command, 3)

    monkeypatch.setattr(typecheck.subprocess, "run", fake_run)
    assert typecheck.main(["--no-incremental"]) == 3
    assert seen["linked"]
    assert seen["command"][-3:] == ["-p", "repoagent", "--no-incremental"]
