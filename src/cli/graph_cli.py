"""Graph inspection and Obsidian export commands (M4)."""

from pathlib import Path
from typing import Annotated

import typer

from repoagent.cli.runtime import client, errors, output
from repoagent.graph.inspection import graph_inspection, graph_summary
from repoagent.graph.store import store_from_snapshot

Json = Annotated[bool, typer.Option("--json", help="Write structured JSON to stdout.")]
Symbol = Annotated[
    str | None, typer.Option("--symbol", help="Inspect one qualified symbol.")
]


def register_graph(app: typer.Typer) -> None:
    @app.command("graph")
    def graph(
        ctx: typer.Context,
        source: str,
        symbol: Symbol = None,
        json: Json = False,
    ) -> None:
        """Inspect the repository code knowledge graph (M4)."""
        with errors():
            retrieval = client(ctx).retrieval()
            if symbol:
                snapshot = retrieval.graph(source)
                inspection = graph_inspection(
                    store_from_snapshot(snapshot), snapshot, symbol
                )
                output(inspection, as_json=json)
                return
            snapshot = retrieval.graph(source)
            if json:
                output(snapshot, as_json=True)
                return
            output(graph_summary(snapshot, Path(source).name), as_json=False)

    @app.command("export-obsidian")
    def export_obsidian(
        ctx: typer.Context,
        source: str,
        destination: Path,
        overwrite: Annotated[
            bool,
            typer.Option("--overwrite", help="Export into a non-empty directory."),
        ] = False,
        json: Json = False,
    ) -> None:
        """Export the repository graph as an Obsidian vault (M4)."""
        with errors():
            summary = (
                client(ctx)
                .retrieval()
                .export_obsidian(source, destination, overwrite=overwrite)
            )
            output(summary, as_json=json)
