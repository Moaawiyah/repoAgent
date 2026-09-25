"""Repository audit CLI: discover, verify, and optionally repair issues."""

from typing import Annotated

import typer

from repoagent.cli.audit_render import render_audit
from repoagent.cli.runtime import client, errors, output
from repoagent.domain.audit_report import AuditReport

Json = Annotated[bool, typer.Option("--json", help="Write structured JSON to stdout.")]


def register_audit(app: typer.Typer) -> None:
    @app.command()
    def audit(
        ctx: typer.Context,
        source: str,
        limit: Annotated[
            int | None,
            typer.Option("--limit", min=1, max=200, help="Max candidates verified."),
        ] = None,
        repair: Annotated[
            bool,
            typer.Option(
                "--repair",
                help="Send the top verified finding into the repair pipeline.",
            ),
        ] = False,
        execute: Annotated[
            bool,
            typer.Option(
                "--execute",
                help="With --repair: validate the repair in a disposable Docker "
                "sandbox copy (M7: review, tests, retries).",
            ),
        ] = False,
        max_attempts: Annotated[
            int | None, typer.Option("--max-attempts", min=1, max=10)
        ] = None,
        timeout: Annotated[
            int | None, typer.Option("--timeout", min=1, max=3600, help="Seconds.")
        ] = None,
        json: Json = False,
    ) -> None:
        """Discover evidence-backed candidate issues; never modifies the repository."""
        if (execute and not repair) or (
            not execute and (max_attempts is not None or timeout is not None)
        ):
            typer.echo(
                "Invalid input: --execute requires --repair, and "
                "--max-attempts/--timeout require --execute",
                err=True,
            )
            raise typer.Exit(2)
        with errors():
            report = client(ctx).audit(
                source,
                limit=limit,
                repair=repair,
                execute=execute,
                max_attempts=max_attempts,
                timeout=timeout,
            )
            output(report, json)
            validated = report.validated_repair
            if validated is not None and validated.status != "validated":
                raise typer.Exit(1)


__all__ = ["register_audit", "render_audit", "AuditReport"]
