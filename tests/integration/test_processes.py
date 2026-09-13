"""Installed module invocation and task persistence across real processes."""

import json
import os
import subprocess
import sys


def test_independent_processes_share_task_storage(tmp_path):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("REPOAGENT_")
    }
    command = [sys.executable, "-m", "repoagent", "--data-dir", str(tmp_path / "data")]

    def invoke(*args):
        return subprocess.run(
            [*command, *args],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

    created = invoke("benchmark", "synthetic", "--json")
    assert created.returncode == 3, created.stderr
    task = json.loads(created.stdout)
    fetched = invoke("tasks", "show", task["id"], "--json")
    assert fetched.returncode == 0, fetched.stderr
    assert json.loads(fetched.stdout) == task
    events = invoke("tasks", "events", task["id"], "--json")
    assert events.returncode == 0
    assert [event["sequence"] for event in json.loads(events.stdout)] == [1, 2]
