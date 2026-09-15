"""Static detection of validation commands and dependency specifications."""

from pathlib import Path

from repoagent.domain.sandbox import CommandKind, SandboxLimits
from repoagent.validation.detection import ProjectDetector

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/auth_bug"


def detect(root, **limits):
    return ProjectDetector(SandboxLimits(**limits)).detect(root)


def test_fixture_with_tests_directory_uses_pytest_only():
    plan = detect(FIXTURE)
    assert [c.kind for c in plan.commands] == [CommandKind.PYTEST]
    assert plan.requirements == ["pytest>=8,<9"]


def test_pyproject_configuration_and_dependencies(tmp_path):
    (tmp_path / "pyproject.toml").write_text(
        '[project]\ndependencies = ["requests>=2", "evil @ https://x/y.whl"]\n'
        '[project.optional-dependencies]\ntest = ["pytest-mock"]\n'
        '[dependency-groups]\ndev = ["hypothesis", {include-group = "x"}]\n'
        "[tool.pytest.ini_options]\naddopts = '-p evil'\n[tool.ruff]\n"
    )
    (tmp_path / "requirements.txt").write_text(
        "# comment\n\nattrs==23.1\n-e .\n--index-url http://evil\n"
    )
    plan = detect(tmp_path)
    assert {c.kind for c in plan.commands} == {"pytest", "ruff_check"}
    assert plan.requirements == [
        "pytest>=8,<9",
        "ruff>=0.9,<1",
        "requests>=2",
        "pytest-mock",
        "hypothesis",
        "attrs==23.1",
    ]
    assert "-e ." in plan.skipped_requirements
    assert any("evil" in item for item in plan.skipped_requirements)


def test_tools_strategy_ignores_project_dependencies(tmp_path):
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "requirements.txt").write_text("django\n")
    assert detect(tmp_path, dependencies="tools").requirements == ["pytest>=8,<9"]
    assert detect(tmp_path, dependencies="none").requirements == []


def test_setup_cfg_tox_and_loose_test_files(tmp_path):
    (tmp_path / "setup.cfg").write_text("[tool:pytest]\ntestpaths = t\n")
    assert detect(tmp_path).has(CommandKind.PYTEST)
    other = tmp_path / "other"
    other.mkdir()
    (other / "tox.ini").write_text("[broken\n")
    (other / "test_x.py").write_text("def test(): pass\n")
    assert detect(other).has(CommandKind.PYTEST)


def test_no_tests_and_policy_filtering(tmp_path):
    (tmp_path / "pyproject.toml").write_text("not = [valid")
    (tmp_path / "ruff.toml").write_text("")
    plan = detect(tmp_path, allowed_commands=frozenset({CommandKind.PYTEST}))
    assert not plan.commands and "No pytest" in plan.notes[0]
    assert any("disabled by policy" in note for note in plan.notes)


def test_symlinked_or_oversized_config_is_ignored(tmp_path):
    secret = tmp_path / "outside.toml"
    secret.write_text("[tool.pytest.ini_options]\n")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").symlink_to(secret)
    assert not detect(repo).commands


def test_setup_cfg_install_requires_and_metadata_requires_dist_alias(tmp_path):
    """setup.cfg has two conventions for runtime deps: the standard
    ``[options] install_requires`` and a ``[metadata] requires-dist`` alias
    some real projects (e.g. requests) use instead."""
    (tmp_path / "setup.cfg").write_text(
        "[tool:pytest]\ntestpaths = tests\n"
        "[options]\ninstall_requires =\n    packagea>=1\n    packageb<2\n"
    )
    plan = detect(tmp_path)
    assert "packagea>=1" in plan.requirements and "packageb<2" in plan.requirements

    other = tmp_path / "other"
    other.mkdir()
    (other / "setup.cfg").write_text(
        "[tool:pytest]\ntestpaths = tests\n"
        "[metadata]\nrequires-dist =\n    certifi>=2017.4.17\n    idna>=2.5,<4\n"
    )
    plan = detect(other)
    assert (
        "certifi>=2017.4.17" in plan.requirements
        and "idna>=2.5,<4" in plan.requirements
    )


def test_projects_own_tool_pin_overrides_the_default_and_avoids_conflicts(tmp_path):
    """A project's own pytest constraint wins over RepoAgent's default so
    pip is never asked to satisfy two contradictory pytest ranges at once
    (observed on requests v2.31.0: its own <=6.2.5 vs. our default >=8)."""
    (tmp_path / "setup.cfg").write_text("[tool:pytest]\ntestpaths = tests\n")
    (tmp_path / "requirements-dev.txt").write_text(
        "pytest>=2.8.0,<=6.2.5\nruff==0.5.0\n"
    )
    plan = detect(tmp_path)
    assert plan.requirements.count("pytest>=2.8.0,<=6.2.5") == 1
    assert not any(spec.startswith("pytest>=8") for spec in plan.requirements)
    assert (
        "ruff==0.5.0" in plan.requirements and "ruff>=0.9,<1" not in plan.requirements
    )


def test_no_conflicting_project_pin_still_uses_the_default(tmp_path):
    (tmp_path / "setup.cfg").write_text("[tool:pytest]\ntestpaths = tests\n")
    (tmp_path / "requirements.txt").write_text("attrs==23.1\n")
    assert "pytest>=8,<9" in detect(tmp_path).requirements
