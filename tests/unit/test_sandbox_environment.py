"""Reproducible sandbox environments: pinned dependencies and src-layout imports."""

from pathlib import Path

import pytest

from repoagent.config import Settings
from repoagent.domain.errors import SandboxError
from repoagent.domain.sandbox import SandboxLimits
from repoagent.sandbox.docker_args import DockerCommandBuilder
from repoagent.sdk.validated_repair import pinned_requirements, sandbox_limits
from repoagent.validation.detection import ProjectDetector


def project(tmp_path: Path, src_layout: bool) -> Path:
    (tmp_path / "tests").mkdir()
    (tmp_path / "requirements.txt").write_text("requests>=2\n")
    package = tmp_path / ("src/pkg" if src_layout else "pkg")
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    return tmp_path


def test_pinned_requirements_replace_declared_ranges(tmp_path):
    root = project(tmp_path, src_layout=False)
    declared = ProjectDetector(SandboxLimits()).detect(root)
    assert "requests>=2" in declared.requirements and declared.python_paths == []
    pinned = SandboxLimits(pinned_requirements=("requests==2.31.0", "pytest==8.3.5"))
    plan = ProjectDetector(pinned).detect(root)
    assert "requests==2.31.0" in plan.requirements
    assert "requests>=2" not in plan.requirements
    assert [r for r in plan.requirements if r.startswith("pytest")] == ["pytest==8.3.5"]


def test_src_layout_adds_import_root_to_pythonpath(tmp_path):
    plan = ProjectDetector(SandboxLimits()).detect(project(tmp_path, True))
    assert plan.python_paths == ["src"]
    builder = DockerCommandBuilder(
        "python:3.12-slim", SandboxLimits(), python_paths=plan.python_paths
    )
    argv = builder.run("repoagent-0123456789ab", ["python"], tmp_path, tmp_path, False)
    assert "PYTHONPATH=/deps:/workspace/src" in argv
    with pytest.raises(SandboxError):
        DockerCommandBuilder("python:3.12-slim", SandboxLimits(), python_paths=["../x"])


def test_settings_pins_merge_list_and_requirements_file(tmp_path):
    pins = tmp_path / "pins.txt"
    pins.write_text("# frozen\nattrs==23.1.0\n\nsix==1.16.0\n")
    settings = Settings(
        sandbox_pinned_requirements=["six==1.16.0"], sandbox_requirements_file=pins
    )
    assert pinned_requirements(settings) == ("six==1.16.0", "attrs==23.1.0")
    limits = sandbox_limits(settings, None)
    assert limits.pinned_requirements == ("six==1.16.0", "attrs==23.1.0")
    assert sandbox_limits(Settings(), 5).pinned_requirements == ()
