"""Shared fake git double for GitHub-source tests (fetch + concurrency)."""

from pathlib import Path

from repoagent.sandbox.git import HARDENING, NO_CREDENTIALS
from repoagent.sandbox.process import ProcessResult

SHA = "0123456789abcdef0123456789abcdef01234567"


class FakeGit:
    def __init__(self, fail_on=None, commit=SHA, files=None):
        self.calls, self.fail_on, self.commit = [], fail_on, commit
        self.files = files or {"pkg/mod.py": "x = 1\n"}

    def run(self, argv, timeout, max_output):
        self.calls.append(argv)
        step = argv[len(HARDENING) + len(NO_CREDENTIALS) + 3]
        if step == self.fail_on:
            return ProcessResult(128, "", "fatal", False, False, 0.1)
        if step == "checkout":
            root = argv[argv.index("-C") + 1]
            for name, text in self.files.items():
                path = Path(root) / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
        stdout = self.commit + "\n" if step == "rev-parse" else ""
        return ProcessResult(0, stdout, "", False, False, 0.1)
