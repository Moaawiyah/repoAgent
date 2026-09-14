"""M6 repair CLI command; reports only unapplied static proposals."""

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
        json: Annotated[bool, typer.Option("--json")] = False,
    ) -> None:
        """Generate/review an unapplied patch; never execute target code (M6)."""
        with errors():
            output(client(ctx).repair(source, issue, max_revisions=max_revisions), json)
