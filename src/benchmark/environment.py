"""Per-task sandbox environments and Docker image provenance for benchmarks."""

import subprocess

from repoagent.benchmark.models import BenchmarkTask
from repoagent.config import Settings
from repoagent.ports.sandbox import SandboxRunner
from repoagent.sandbox.docker_runner import DockerSandboxRunner

INSPECT_TIMEOUT = 30


def task_settings(settings: Settings, task: BenchmarkTask) -> Settings:
    """Settings with the task's pinned image and requirements applied."""
    environment = task.environment
    if environment is None:
        return settings
    update: dict = {"sandbox_pinned_requirements": list(environment.requirements)}
    if environment.image:
        update["sandbox_image"] = environment.image
    return settings.model_copy(update=update)


def task_runner(settings: Settings, injected: SandboxRunner | None) -> SandboxRunner:
    """An injected runner (tests) wins; otherwise Docker with the task image."""
    return injected or DockerSandboxRunner(
        settings.sandbox_image, workspace_dir=settings.sandbox_workspace_dir
    )


def image_digest(image: str, docker: str = "docker") -> str | None:
    """Resolve a local image to its immutable ``repo@sha256:`` digest.

    Returns ``None`` when Docker or the image is unavailable, so manifests
    record "unknown" instead of a guessed identity.
    """
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [docker, "image", "inspect", "--format", "{{json .RepoDigests}}", image],
            capture_output=True,
            text=True,
            timeout=INSPECT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    digests = result.stdout.strip().strip("[]").replace('"', "").split(",")
    return digests[0] or None if result.returncode == 0 else None
