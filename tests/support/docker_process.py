"""Fake process runner that stands in for the Docker CLI in unit tests."""

from pathlib import Path

from repoagent.sandbox.process import ProcessResult

PYTEST_OK = "1 passed in 0.10s"


def mount_source(argv, target):
    for index, item in enumerate(argv):
        if item == "--mount" and f"target={target}" in argv[index + 1]:
            fields = dict(
                p.split("=", 1) for p in argv[index + 1].split(",") if "=" in p
            )
            return Path(fields["source"])
    return None


class FakeDockerProcess:
    """Records argv; ``outcomes`` script ``docker run`` results in order."""

    def __init__(self, outcomes=(), probe_exit=0):
        self.calls, self.outcomes, self.probe_exit = [], list(outcomes), probe_exit
        self.seen_files: list[dict[str, str]] = []
        self.workspaces: list[Path] = []

    def run(self, argv, timeout, max_output):
        self.calls.append(list(argv))
        if argv[1] == "version":
            return ProcessResult(self.probe_exit, "27.0", "", False, False, 0.01)
        if argv[1] == "rm":
            return ProcessResult(0, "", "", False, False, 0.01)
        workspace = mount_source(argv, "/workspace")
        if workspace is not None:
            self.workspaces.append(workspace)
            self.seen_files.append(
                {
                    p.relative_to(workspace).as_posix(): p.read_text()
                    for p in workspace.rglob("*.py")
                }
            )
        outcome = self.outcomes.pop(0) if self.outcomes else (0, PYTEST_OK)
        if outcome == "timeout":
            return ProcessResult(None, "", "", True, False, timeout)
        code, stdout = outcome
        return ProcessResult(code, stdout, "err: last line", False, False, 0.2)

    def runs(self):
        return [c for c in self.calls if c[1] == "run"]
