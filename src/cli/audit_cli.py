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
        json: Json = False,
    ) -> None:
        """Discover evidence-backed candidate issues; never modifies the repository."""
        with errors():
            report = client(ctx).audit(source, limit=limit, repair=repair)
            output(report, json)


__all__ = ["register_audit", "render_audit", "AuditReport"]
