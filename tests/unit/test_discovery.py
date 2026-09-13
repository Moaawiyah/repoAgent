"""Repository file discovery: ignores, metadata, symlinks, determinism."""

import os
from pathlib import Path

import pytest

from repoagent.analysis.discovery import FileDiscovery


def make_tree(root: Path) -> None:
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("")
    (root / "app" / "util.py").write_text("")
    (root / "README.md").write_text("# demo\n")
    (root / ".gitignore").write_text("secret.txt\nskipped/\n")
    (root / "secret.txt").write_text("s")
    (root / "skipped").mkdir()
    (root / "skipped" / "x.py").write_text("")
    for folder in (".venv", "__pycache__", "build"):
        (root / folder).mkdir()
        (root / folder / "ignored.py").write_text("")


def test_discovers_python_and_metadata_ignoring_directories(tmp_path):
    root = tmp_path / "repo"
    make_tree(root)
    result = FileDiscovery(root).discover()
    assert set(result.python_files) == {"app/__init__.py", "app/util.py"}
    assert result.metadata_files == ("README.md",)
    assert result.file_count == 4


def test_discovery_is_deterministic(tmp_path):
    root = tmp_path / "repo"
    make_tree(root)
    assert FileDiscovery(root).discover() == FileDiscovery(root).discover()


def test_symlinked_files_inside_root_are_included(tmp_path):
    root = tmp_path / "repo"
    make_tree(root)
    (root / "link.py").symlink_to(root / "app" / "util.py")
    assert "link.py" in FileDiscovery(root).discover().python_files


def test_symlinks_leaving_root_and_links_to_directories_are_skipped(tmp_path):
    root = tmp_path / "repo"
    make_tree(root)
    outside = tmp_path / "outside.py"
    outside.write_text("x = 1\n")
    (root / "outside_link.py").symlink_to(outside)
    (root / "dir_link").symlink_to(root / "app")
    (root / "broken_link.py").symlink_to(root / "missing-target")
    result = FileDiscovery(root).discover()
    assert "outside_link.py" not in result.python_files
    assert "dir_link" not in result.python_files
    assert "broken_link.py" not in result.python_files
    assert outside.read_text() == "x = 1\n"


def test_nested_gitignore_rules_apply_per_directory(tmp_path):
    root = tmp_path / "repo"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / ".gitignore").write_text("gen.py\n")
    (root / "sub" / "gen.py").write_text("")
    (root / "sub" / "keep.py").write_text("")
    result = FileDiscovery(root).discover()
    assert result.python_files == ("sub/keep.py",)
    assert result.file_count == 2


def test_unreadable_gitignore_and_directories_are_skipped(tmp_path):
    root = tmp_path / "repo"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / ".gitignore").mkdir()
    (root / "sub" / "keep.py").write_text("")
    locked = root / "locked"
    locked.mkdir()
    (locked / "hidden.py").write_text("")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        locked.rmdir()
        locked.mkdir(mode=0o755)
        (locked / "visible.py").write_text("")
        result = FileDiscovery(root).discover()
    else:
        locked.chmod(0o000)
        try:
            result = FileDiscovery(root).discover()
        finally:
            locked.chmod(0o755)
    assert "sub/keep.py" in result.python_files
    assert not any(path.startswith("locked") for path in result.python_files)


@pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() != 0,
    reason="root-specific discovery behavior",
)
def test_root_can_read_locked_directories(tmp_path):
    root = tmp_path / "repo"
    locked = root / "locked"
    locked.mkdir(parents=True)
    (locked / "visible.py").write_text("")
    assert FileDiscovery(root).discover().python_files == ("locked/visible.py",)
