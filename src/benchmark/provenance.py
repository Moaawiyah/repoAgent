"""Run manifests recording what is needed to reproduce results (no secrets)."""

import hashlib
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.benchmark.environment import image_digest
from repoagent.benchmark.experiment import ExperimentConfig
from repoagent.benchmark.models import BenchmarkSuite
from repoagent.config import Settings

SOURCE_ROOT = Path(__file__).resolve().parents[2]


class RunManifest(AnalysisModel):
    run_id: str = Field(pattern=r"^\d{8}T\d{6}Z-[0-9a-f]{6}$")
    suite: str
    suite_source: str
    suite_sha256: str
    task_ids: list[str]
    experiments: list[ExperimentConfig]
    repoagent_version: str
    repoagent_commit: str | None
    repoagent_dirty: bool | None
    llm_provider: str
    llm_model: str
    embedding: str
    sandbox_image: str
    # Immutable identity of the default image and each task's pinned image.
    sandbox_image_digest: str | None = None
    task_images: dict[str, str] = Field(default_factory=dict)
    python: str
    platform: str
    started_at: datetime
    finished_at: datetime | None = None


def _embedding(settings: Settings) -> str:
    if settings.embedding_provider == "hashing":
        return f"hashing:{settings.embedding_dimension}"
    return f"{settings.embedding_provider}:{settings.embedding_model}"


def new_run_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid4().hex[:6]}"


def _git(*args: str) -> str | None:
    if not (SOURCE_ROOT / ".git").exists():
        return None
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, trusted RepoAgent checkout
            ["git", "-C", str(SOURCE_ROOT), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def build_manifest(
    suite: BenchmarkSuite,
    task_ids: list[str],
    experiments: list[ExperimentConfig],
    settings: Settings,
    provider_name: str | None,
) -> RunManifest:
    from repoagent import __version__

    status = _git("status", "--porcelain", "--untracked-files=no")
    return RunManifest(
        run_id=new_run_id(),
        suite=suite.name,
        suite_source=suite.source,
        suite_sha256=hashlib.sha256(suite.model_dump_json().encode()).hexdigest(),
        task_ids=task_ids,
        experiments=experiments,
        repoagent_version=__version__,
        repoagent_commit=_git("rev-parse", "HEAD"),
        repoagent_dirty=None if status is None else bool(status),
        llm_provider=provider_name or settings.llm_provider,
        llm_model=settings.llm_model
        if (provider_name or settings.llm_provider) != "none"
        else "",
        embedding=_embedding(settings),
        sandbox_image=settings.sandbox_image,
        sandbox_image_digest=image_digest(settings.sandbox_image)
        if any(config.mode == "repair" for config in experiments)
        else None,
        task_images={
            task.task_id: task.environment.image
            for task in suite.select(task_ids)
            if task.environment and task.environment.image
        },
        python=platform.python_version(),
        platform=platform.platform(),
        started_at=datetime.now(UTC),
    )
