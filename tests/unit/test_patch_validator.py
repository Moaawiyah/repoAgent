"""M6 static patch validation never writes to a target tree."""

from pathlib import Path

import pytest

from repoagent.adapters.patch_validator import StaticPatchValidator
from tests.support.repair_provider import DIFF


@pytest.fixture
def repository(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    target = path / "main.py"
    target.write_text("def value():\n    return 1\n")
    return path


def patch(path, before, after):
    return f"--- a/{path}\n+++ b/{path}\n@@ -1,1 +1,1 @@\n-{before}\n+{after}\n"


def test_valid_patch_is_applied_only_in_memory(repository):
    before = (repository / "main.py").read_bytes()
    result = StaticPatchValidator(repository).validate(
        patch("main.py", "    return 1", "    return 2")
    )
    assert result.valid and result.changed_lines == 2
    assert (repository / "main.py").read_bytes() == before


@pytest.mark.parametrize(
    "diff, message",
    [
        ("not a diff", "unified"),
        (patch("../secret.py", "x", "y"), "Unsafe"),
        (patch("missing.py", "x", "y"), "unavailable"),
        ("GIT binary patch", "non-binary"),
        (patch("main.py", "    return 9", "    return 2"), "context"),
    ],
)
def test_rejects_invalid_or_unsafe_patches(repository, diff, message):
    result = StaticPatchValidator(repository).validate(diff)
    assert not result.valid and message.casefold() in result.errors[0].casefold()


def test_rejects_invalid_python(repository):
    result = StaticPatchValidator(repository).validate(
        patch("main.py", "    return 1", "    return (")
    )
    assert not result.valid and "never closed" in result.errors[0].casefold()


def test_auth_fixture_patch_is_valid_and_unchanged():
    root = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"
    target = root / "app/users/repository.py"
    before = target.read_bytes()
    assert StaticPatchValidator(root).validate(DIFF).valid
    assert target.read_bytes() == before
