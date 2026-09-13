"""Repository operation command registration."""

from typing import Annotated

import typer

from repoagent.cli.runtime import errors, output, service
from repoagent.domain.repository import RepositorySpec
from repoagent.domain.tasks import TaskKind, TaskRequest

Commit = Annotated[str | None, typer.Option(help="Requested revision; inert in M1.")]
Json = Annotated[bool, typer.Option("--json", help="Write structured JSON to stdout.")]


def submit(
    ctx: typer.Context,
    kind: TaskKind,
    source: str,
    description: str | None,
    commit: str | None,
    as_json: bool,
) -> None:
    with errors():
        request = TaskRequest(
            kind=kind,
            repository=RepositorySpec(source=source, commit=commit),
            description=description,
        )
        result = service(ctx).submit(request)
        output(result, as_json)
    raise typer.Exit(3)


def register(app: typer.Typer) -> None:
    @app.command()
    def index(
        ctx: typer.Context, source: str, commit: Commit = None, json: Json = False
    ) -> None:
        """Index a repository (unavailable until M3)."""
        submit(ctx, TaskKind.INDEX, source, None, commit, json)

    @app.command()
    def analyze(
        ctx: typer.Context, source: str, commit: Commit = None, json: Json = False
    ) -> None:
        """Analyze repository structure (unavailable until M2)."""
        submit(ctx, TaskKind.ANALYZE, source, None, commit, json)

    @app.command()
    def ask(
        ctx: typer.Context,
        source: str,
        question: str,
        commit: Commit = None,
        json: Json = False,
    ) -> None:
        """Ask an evidence-grounded question (unavailable until M5)."""
        submit(ctx, TaskKind.ASK, source, question, commit, json)

    @app.command()
    def fix(
        ctx: typer.Context,
        source: str,
        issue: str,
        commit: Commit = None,
        json: Json = False,
    ) -> None:
        """Generate and validate a repair (unavailable until M7)."""
        submit(ctx, TaskKind.FIX, source, issue, commit, json)

    @app.command()
    def test(
        ctx: typer.Context, source: str, commit: Commit = None, json: Json = False
    ) -> None:
        """Validate a repository in isolation (unavailable until M7)."""
        submit(ctx, TaskKind.TEST, source, None, commit, json)

    @app.command()
    def benchmark(ctx: typer.Context, suite: str, json: Json = False) -> None:
        """Run synthetic, bugsinpy, swe-bench or swe-bench-verified (M9)."""
        with errors():
            request = TaskRequest(kind=TaskKind.BENCHMARK, suite=suite)
            output(service(ctx).submit(request), json)
        raise typer.Exit(3)
