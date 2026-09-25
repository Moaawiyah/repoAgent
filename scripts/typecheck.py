"""Run mypy on the ``repoagent`` package (``src/`` installs as ``repoagent``).

The editable install maps ``repoagent`` to ``src/`` through an import hook
that mypy cannot follow, which silently turns every cross-module import
into ``Any``. A temporary ``repoagent -> src`` symlink root gives mypy the
real package so types are checked across modules.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    with tempfile.TemporaryDirectory(prefix="repoagent-typecheck-") as temporary:
        (Path(temporary) / "repoagent").symlink_to(ROOT / "src")
        env = {**os.environ, "MYPYPATH": temporary}
        command = [sys.executable, "-m", "mypy", "-p", "repoagent", *(argv or [])]
        return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
