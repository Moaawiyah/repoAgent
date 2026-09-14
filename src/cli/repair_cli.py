"""Repair CLI: static proposals by default, sandboxed validation with --execute."""

from typing import Annotated

import typer

from repoagent.cli.runtime import client, errors, output


def register_repair(app: typer.Typer) -> None:
    @app.command()
    def repair(
        ctx: typer.Context,
        source: str,
        issue: str,
        max_revisions: Annotated[int | None, typer.Option("--max-revisions")] = None,
        execute: Annotated[
            bool,
            typer.Option(
                "--execute",
                help="Apply the patch to a disposable Docker sandbox copy and run "
                "detected validation (M7). Without it nothing is executed.",
            ),
        ] = False,
        max_attempts: Annotated[
            int | None, typer.Option("--max-attempts", min=1, max=10)
        ] = None,
        timeout: Annotated[
            int | None, typer.Option("--timeout", min=1, max=3600, help="Seconds.")
        ] = None,
        json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Generate/review a patch; only --execute runs target code, sandboxed."""
        with errors():
            agent = client(ctx)
            if not execute:
                if max_attempts is not None or timeout is not None:
                    typer.echo(
                        "Invalid input: --max-attempts/--timeout require --execute",
                        err=True,
                    )
                    raise typer.Exit(2)
                output(agent.repair(source, issue, max_revisions=max_revisions), json)
                return
            report = agent.repair_and_validate(
                source,
                issue,
                max_attempts=max_attempts,
                max_revisions=max_revisions,
                timeout=timeout,
            )
            output(report, json)
            if report.status != "validated":
                raise typer.Exit(1)
