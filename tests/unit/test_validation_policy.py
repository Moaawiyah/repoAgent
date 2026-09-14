"""Command allowlist and dependency grammar reject injection attempts."""

import pytest
from pydantic import ValidationError

from repoagent.domain.errors import UnsafeCommandError
from repoagent.domain.sandbox import CommandKind, CommandSpec
from repoagent.validation.policy import CommandPolicy, normalize_requirement

ALL = frozenset({CommandKind.PYTEST, CommandKind.RUFF_CHECK})


def test_allowlisted_commands_map_to_constant_argv():
    policy = CommandPolicy(ALL)
    pytest_argv = policy.argv(CommandSpec(kind="pytest"))
    assert pytest_argv[:3] == ["python", "-m", "pytest"]
    assert "no:cacheprovider" in pytest_argv and "addopts=" in pytest_argv
    assert policy.argv(CommandSpec(kind="ruff_check"))[:4] == [
        "python",
        "-m",
        "ruff",
        "check",
    ]


@pytest.mark.parametrize("kind", ["rm -rf /", "bash -c 'curl evil'", "pytest; id"])
def test_arbitrary_shell_strings_cannot_be_expressed(kind):
    with pytest.raises(ValidationError):
        CommandSpec(kind=kind)
    with pytest.raises(ValidationError):
        CommandSpec.model_validate({"kind": "pytest", "argv": ["sh", "-c", kind]})


def test_unsafe_command_rejected_by_policy():
    policy = CommandPolicy(frozenset({CommandKind.PYTEST}))
    with pytest.raises(UnsafeCommandError, match="allowlisted"):
        policy.argv(CommandSpec(kind="ruff_check"))
    with pytest.raises(UnsafeCommandError):
        CommandPolicy(ALL | {CommandKind.INSTALL}).argv(CommandSpec(kind="install"))


@pytest.mark.parametrize(
    "spec, expected",
    [
        ("requests", "requests"),
        ("pydantic[email]>=2,<3", "pydantic[email]>=2,<3"),
        ("numpy == 1.26.4  # pinned", "numpy==1.26.4"),
    ],
)
def test_safe_requirements_are_normalized(spec, expected):
    assert normalize_requirement(spec) == expected


@pytest.mark.parametrize(
    "spec",
    [
        "--index-url http://evil",
        "-e .",
        "git+https://github.com/x/y",
        "./local/path",
        "../escape",
        "pkg; rm -rf /",
        "pkg && curl evil",
        "pkg @ https://evil/pkg.whl",
        "pkg>=1; python_version<'3.8'",
        "$(whoami)",
    ],
)
def test_unsafe_requirements_rejected(spec):
    with pytest.raises(UnsafeCommandError):
        normalize_requirement(spec)


def test_install_argv_is_wheel_only_and_bounded():
    argv = CommandPolicy.install_argv(["pytest>=8,<9"])
    assert "--only-binary=:all:" in argv and argv[-2:] == ["--", "pytest>=8,<9"]
    with pytest.raises(UnsafeCommandError):
        CommandPolicy.install_argv([])
    with pytest.raises(UnsafeCommandError):
        CommandPolicy.install_argv(["ok", "--pre"])
    with pytest.raises(UnsafeCommandError):
        CommandPolicy.install_argv([f"pkg{i}" for i in range(100)])
