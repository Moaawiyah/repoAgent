"""Obsidian vault export: the graph is the source of truth, Markdown only.

The exporter writes deterministic standard Markdown. Repository-controlled
text is confined to code spans and injection-safe fenced blocks; links are
created only for real graph relationships; destinations are never deleted
and require explicit ``overwrite`` intent when non-empty.
"""

import logging
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from repoagent.domain.errors import ExportError
from repoagent.export.notes import (
    FOLDERS_BY_TYPE,
    render_note,
    render_repository_note,
    safe_name,
)
from repoagent.graph.models import GraphNode, GraphSnapshot


class ExportSummary(BaseModel):
    """Typed result of an Obsidian vault export."""

    model_config = ConfigDict(frozen=True)
    repository: str
    destination: str
    notes: int
    links: int
    edge_count: int


class ObsidianExporter:
    """Exports a repository graph as an Obsidian-compatible vault."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def export(
        self,
        graph: GraphSnapshot,
        destination: Path,
        *,
        overwrite: bool = False,
    ) -> ExportSummary:
        """Write the vault; never deletes, guards non-empty destinations."""
        vault = destination.expanduser().resolve()
        if vault.exists() and any(vault.iterdir()) and not overwrite:
            raise ExportError(
                "Destination is not empty; pass overwrite to export into it"
            )
        vault.mkdir(parents=True, exist_ok=True)
        nodes = {node.node_id: node for node in graph.nodes}
        outgoing, incoming = _adjacency(graph)
        notes = 0
        for node in graph.nodes:
            target = self._note_path(vault, node)
            target.write_text(
                render_note(
                    node,
                    nodes,
                    outgoing[node.node_id],
                    incoming[node.node_id],
                    self._root,
                ),
                encoding="utf-8",
            )
            notes += 1
        (vault / "Repository.md").write_text(
            render_repository_note(graph, nodes), encoding="utf-8"
        )
        logging.getLogger(__name__).info(
            "Obsidian export completed", extra={"event": "obsidian_exported"}
        )
        return ExportSummary(
            repository=vault.name,
            destination=str(vault),
            notes=notes + 1,
            links=self._link_count(graph),
            edge_count=len(graph.edges),
        )

    def _note_path(self, vault: Path, node: GraphNode) -> Path:
        folder = FOLDERS_BY_TYPE[node.node_type]
        target = vault / folder / f"{safe_name(node.node_id)}.md"
        if not target.resolve().is_relative_to(vault):
            raise ExportError("Note path escapes the vault directory")
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    def _link_count(self, graph: GraphSnapshot) -> int:
        internal = [edge for edge in graph.edges if edge.resolved]
        return 2 * len(internal)


def _adjacency(
    graph: GraphSnapshot,
) -> tuple[dict[str, list], dict[str, list]]:
    outgoing: dict[str, list] = {}
    incoming: dict[str, list] = {}
    for node in graph.nodes:
        outgoing[node.node_id] = []
        incoming[node.node_id] = []
    for edge in graph.edges:
        if edge.source in outgoing:
            outgoing[edge.source].append(edge)
        if edge.target in incoming:
            incoming[edge.target].append(edge)
    return outgoing, incoming


__all__ = ["ExportSummary", "ObsidianExporter"]
