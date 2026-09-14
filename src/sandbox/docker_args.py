"""Hardened ``docker run`` argument construction (Docker-specific adapter)."""

import os
import re
from pathlib import Path

from repoagent.domain.errors import SandboxError
from repoagent.domain.sandbox import SandboxLimits
from repoagent.validation.policy import DEPS_MOUNT, WORKSPACE_MOUNT

_IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/:@-]{0,254}$")
_NAME = re.compile(r"^repoagent-[a-f0-9]{8,32}$")
NOBODY = "65534:65534"
TMPFS = "/tmp:rw,nosuid,nodev,size=256m"
MAX_FILE_BYTES = 268_435_456
CONTAINER_ENV = {
    "HOME": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
    "PYTHONPATH": DEPS_MOUNT,
    "PIP_NO_CACHE_DIR": "1",
}


def _mount(source: Path, target: str, readonly: bool) -> str:
    text = str(source)
    if any(character in text for character in ",\n\r=\"'"):
        raise SandboxError("Sandbox mount path contains unsupported characters")
    return f"type=bind,source={text},target={target}" + (
        ",readonly" if readonly else ""
    )


def validate_image(image: str) -> str:
    """Accept only plain image references; no flags or whitespace."""
    if not _IMAGE.fullmatch(image):
        raise SandboxError("Invalid sandbox image reference")
    return image


def container_user() -> str:
    """Run as the invoking non-root user so the copy is writable, else nobody."""
    uid, gid = getattr(os, "getuid", lambda: 0)(), getattr(os, "getgid", lambda: 0)()
    return NOBODY if uid == 0 else f"{uid}:{gid}"


class DockerCommandBuilder:
    """No host directories besides the disposable copy and dependency dir."""

    def __init__(
        self, image: str, limits: SandboxLimits, docker: str = "docker"
    ) -> None:
        self._image, self._limits = validate_image(image), limits
        self._docker = docker

    def run(
        self,
        name: str,
        argv: list[str],
        deps: Path,
        workspace: Path | None,
        network: bool,
    ) -> list[str]:
        if not _NAME.fullmatch(name):
            raise SandboxError("Invalid sandbox container name")
        limits = self._limits
        args = [self._docker, "run", "--rm", "--init", "--name", name]
        args += ["--network", "bridge" if network else "none"]
        args += ["--read-only", "--tmpfs", TMPFS, "--cap-drop", "ALL"]
        args += ["--security-opt", "no-new-privileges", "--user", container_user()]
        args += ["--memory", f"{limits.memory_mb}m", "--memory-swap"]
        args += [f"{limits.memory_mb}m", "--cpus", str(limits.cpus)]
        args += ["--pids-limit", str(limits.pids_limit)]
        args += ["--ulimit", "nofile=1024:1024"]
        if workspace is not None:
            args += ["--ulimit", f"fsize={MAX_FILE_BYTES}:{MAX_FILE_BYTES}"]
            args += ["--mount", _mount(workspace, WORKSPACE_MOUNT, readonly=False)]
            args += ["--workdir", WORKSPACE_MOUNT]
        args += ["--mount", _mount(deps, DEPS_MOUNT, readonly=workspace is not None)]
        for key, value in CONTAINER_ENV.items():
            args += ["--env", f"{key}={value}"]
        return [*args, self._image, *argv]

    def kill(self, name: str) -> list[str]:
        return [self._docker, "rm", "--force", name]

    def probe(self) -> list[str]:
        return [self._docker, "version", "--format", "{{.Server.Version}}"]
