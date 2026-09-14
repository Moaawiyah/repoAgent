"""Disposable workspace copies, in-workspace patching, and fingerprints."""

import os

import pytest

from repoagent.domain.errors import WorkspaceError
from repoagent.sandbox.patching import WorkspacePatcher
from repoagent.sandbox.workspace import WorkspaceLimits, WorkspaceManager, fingerprint

PATCH = "--- a/app.py\n+++ b/app.py\n@@ -1,1 +1,1 @@\n-VALUE = 1\n+VALUE = 2\n"


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    (root / "pkg").mkdir(parents=True)
    (root / "app.py").write_text("VALUE = 1\n")
    (root / "pkg/mod.py").write_text("X = 1\n")
    (root / ".env").write_text("API_KEY=secret\n")
    (root / ".env.example").write_text("API_KEY=\n")
    (root / "id_rsa").write_text("private\n")
    (root / ".git").mkdir()
    (root / ".git/config").write_text("[credential]\n")
    outside = tmp_path / "host-secret.txt"
    outside.write_text("host data\n")
    (root / "link.txt").symlink_to(outside)
    (root / "linkdir").symlink_to(tmp_path)
    os.mkfifo(root / "pipe")
    return root


def manager(tmp_path, **limits):
    return WorkspaceManager(tmp_path / "ws", WorkspaceLimits(**limits))


def test_copy_excludes_links_secrets_vcs_and_special_files(tmp_path, repo):
    workspace = manager(tmp_path).create(repo)
    copied = {
        p.relative_to(workspace.path).as_posix() for p in workspace.path.rglob("*")
    }
    assert {"app.py", "pkg", "pkg/mod.py", ".env.example"} <= copied
    for excluded in (".env", "id_rsa", ".git", "link.txt", "linkdir", "pipe"):
        assert excluded not in copied
    assert not any(p.is_symlink() for p in workspace.path.rglob("*"))
    assert {"link.txt", ".env", "pipe"} <= set(workspace.skipped)
    assert WorkspaceManager.destroy(workspace) and not workspace.root.exists()


def test_patch_applies_to_copy_only(tmp_path, repo):
    before = fingerprint(repo)
    workspace = manager(tmp_path).create(repo)
    assert WorkspacePatcher().apply(workspace.path, PATCH) == ["app.py"]
    assert (workspace.path / "app.py").read_text() == "VALUE = 2\n"
    assert (repo / "app.py").read_text() == "VALUE = 1\n"
    assert fingerprint(repo) == before


@pytest.mark.parametrize(
    "diff",
    [
        PATCH.replace("-VALUE = 1", "-VALUE = 9"),
        PATCH.replace("b/app.py", "b/../app.py"),
        "not a diff",
        PATCH.replace("+VALUE = 2", "+VALUE = ("),
    ],
)
def test_patch_that_cannot_apply_raises_structured_error(tmp_path, repo, diff):
    workspace = manager(tmp_path).create(repo)
    with pytest.raises(WorkspaceError, match="did not apply"):
        WorkspacePatcher().apply(workspace.path, diff)


def test_size_limits_abort_and_clean_up(tmp_path, repo):
    with pytest.raises(WorkspaceError, match="size limits"):
        manager(tmp_path, max_files=1).create(repo)
    assert not any((tmp_path / "ws").iterdir())


def test_workspace_rejects_missing_repository_and_nested_location(tmp_path, repo):
    with pytest.raises(WorkspaceError):
        manager(tmp_path).create(tmp_path / "missing")
    with pytest.raises(WorkspaceError, match="outside"):
        WorkspaceManager(repo / "inner", WorkspaceLimits()).create(repo)


def test_fingerprint_detects_modification(repo):
    before = fingerprint(repo)
    (repo / "app.py").write_text("VALUE = 3\n")
    assert fingerprint(repo) != before
    assert fingerprint(repo, limit=1) == fingerprint(repo, limit=1)
