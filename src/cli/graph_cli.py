"""Graph inspection and Obsidian export commands (M4)."""

from pathlib import Path
from typing import Annotated

import typer

from repoagent.cli.runtime import client, errors, output
from repoagent.domain.errors import RetrievalError
from repoagent.graph.models import EdgeType, GraphInspection, GraphSummary
from repoagent.graph.store import store_from_snapshot

Json = Annotated[bool, typer.Option("--json", help="Write structured JSON to stdout.")]
Symbol = Annotated[
    str | None, typer.Option("--symbol", help="Inspect one qualified symbol.")
]


def _summary(snapshot, repository: str) -> GraphSummary:
    node_counts: dict[str, int] = {}
    for node in snapshot.nodes:
        node_counts[node.node_type.value] = node_counts.get(node.node_type.value, 0) + 1
    edge_counts: dict[str, int] = {}
    for edge in snapshot.edges:
        edge_counts[edge.edge_type.value] = edge_counts.get(edge.edge_type.value, 0) + 1
    return GraphSummary(
        repository=repository,
        node_count=len(snapshot.nodes),
        edge_count=len(snapshot.edges),
        nodes_by_type=node_counts,
        edges_by_type=edge_counts,
    )


def _inspection(store, snapshot, symbol: str) -> GraphInspection:
    if not store.has_node(symbol):
        raise RetrievalError(f"Symbol not found in graph: {symbol}")
    structural = {EdgeType.CONTAINS, EdgeType.DEFINES}
    return GraphInspection(
        symbol=symbol,
        node=store.get_node(symbol),
        outgoing=store.outgoing(symbol),
        incoming=[
            edge for edge in store.incoming(symbol) if edge.edge_type not in structural
        ],
        parents=[
            edge for edge in store.incoming(symbol) if edge.edge_type in structural
        ],
    )


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
                inspection = _inspection(
                    store_from_snapshot(snapshot), snapshot, symbol
                )
                output(inspection, as_json=json)
                return
            snapshot = retrieval.graph(source)
            if json:
                output(snapshot, as_json=True)
                return
            output(_summary(snapshot, Path(source).name), as_json=False)

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
