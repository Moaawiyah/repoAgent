"""Investigation command (M5)."""

from pathlib import Path
from typing import Annotated

import typer

from repoagent.cli.investigation_render import render_investigation
from repoagent.cli.runtime import client, errors, output
from repoagent.domain.investigation import InvestigationReport
from repoagent.export.investigation import export_investigation_note

Json = Annotated[bool, typer.Option("--json", help="Write structured JSON to stdout.")]


def register_investigate(app: typer.Typer) -> None:
    @app.command()
    def investigate(
        ctx: typer.Context,
        source: str,
        issue: str,
        max_iterations: Annotated[
            int | None, typer.Option("--max-iterations", help="Investigation rounds.")
        ] = None,
        top_k: Annotated[
            int, typer.Option("--top-k", help="Results per retrieval.")
        ] = 5,
        export_obsidian: Annotated[
            Path | None,
            typer.Option(
                "--export-obsidian", help="Also write a vault investigation note."
            ),
        ] = None,
        overwrite: Annotated[
            bool,
            typer.Option("--overwrite", help="Replace an existing vault note."),
        ] = False,
        json: Json = False,
    ) -> None:
        """Investigate an issue with the read-only agent (M5)."""
        with errors():
            report = client(ctx).investigate(
                source, issue, max_iterations=max_iterations, top_k=top_k
            )
            if export_obsidian is not None:
                export_investigation_note(report, export_obsidian, overwrite=overwrite)
            output(report, json)
            if report.termination_reason == "provider_error":
                raise typer.Exit(1)


__all__ = ["register_investigate", "render_investigation", "InvestigationReport"]
