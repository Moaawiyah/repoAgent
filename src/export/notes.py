"""Deterministic Obsidian note rendering from repository graph data."""

import re
from pathlib import Path

from repoagent.graph.models import EdgeType, GraphNode, GraphSnapshot, NodeType

FOLDERS_BY_TYPE = {
    NodeType.MODULE: "Modules",
    NodeType.CLASS: "Classes",
    NodeType.FUNCTION: "Functions",
    NodeType.METHOD: "Methods",
}
_RELATION_LABELS = {
    EdgeType.CALLS: ("Calls", "Called by"),
    EdgeType.INHERITS: ("Inherits", "Inherited by"),
    EdgeType.CONTAINS: ("Contains", "Contained by"),
    EdgeType.DEFINES: ("Defines", "Defined by"),
    EdgeType.IMPORTS: ("Imports", "Imported by"),
}
_UNSAFE = re.compile(r"[^A-Za-z0-9_.-]")


def safe_name(qualified: str) -> str:
    """Reduce an identifier to a filesystem-safe Obsidian note name."""
    return _UNSAFE.sub("_", qualified).strip(".") or "unnamed"


def build_filenames(nodes: list[GraphNode]) -> dict[str, str]:
    """Assign each node a vault-unique filename stem, deterministically.

    ``nodes`` must already be in stable order (``GraphSnapshot`` sorts by
    node ID). Distinct node IDs that sanitize to the same name are kept
    distinct with a deterministic ``-2``, ``-3``, ... suffix instead of
    silently overwriting one another's note.
    """
    used: dict[str, int] = {}
    filenames: dict[str, str] = {}
    for node in nodes:
        base = safe_name(node.node_id)
        count = used.get(base, 0) + 1
        used[base] = count
        filenames[node.node_id] = base if count == 1 else f"{base}-{count}"
    return filenames


def link(node_id: str, nodes: dict[str, GraphNode], filenames: dict[str, str]) -> str:
    """Wikilink to existing notes; unresolved names stay inline code."""
    if node_id in nodes:
        return f"[[{filenames[node_id]}]]"
    return f"`{node_id}`"


def render_note(
    node: GraphNode,
    nodes: dict[str, GraphNode],
    outgoing: list,
    incoming: list,
    root: Path,
    filenames: dict[str, str],
) -> str:
    """Render one symbol note with metadata, relationships, and source."""
    parent = link(node.parent, nodes, filenames) if node.parent else "-"
    lines = [
        f"# {node.node_id}",
        "",
        f"**Type:** {node.node_type.value}  ",
        f"**File:** `{node.file_path}`  ",
        f"**Lines:** {node.start_line}-{node.end_line}  ",
        f"**Parent:** {parent}",
    ]
    sections = _sections(outgoing, incoming, nodes, filenames)
    if sections:
        lines.extend(["", "## Relationships", *sections])
    block = source_block(root, node)
    if block:
        lines.extend(["", "## Source", "", block])
    return "\n".join(lines).rstrip() + "\n"


def _sections(
    outgoing: list,
    incoming: list,
    nodes: dict[str, GraphNode],
    filenames: dict[str, str],
) -> list[str]:
    lines: list[str] = []
    for edge_type in EdgeType:
        for edges, direction in ((outgoing, 0), (incoming, 1)):
            label = _RELATION_LABELS[edge_type][direction]
            targets = [
                link(edge.target if direction == 0 else edge.source, nodes, filenames)
                if edge.resolved
                else f"`{edge.target if direction == 0 else edge.source}`"
                for edge in edges
                if edge.edge_type is edge_type
            ]
            if targets:
                lines.append(f"{label}:")
                lines.extend(f"- {target}" for target in targets)
    return lines


def source_block(root: Path, node: GraphNode) -> str | None:
    """Fence the node's source with an injection-safe fence length."""
    try:
        lines = (root / node.file_path).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return None
    chunk = "\n".join(lines[node.start_line - 1 : node.end_line])
    if not chunk.strip():
        return None
    longest = max((len(run) for run in re.findall(r"`+", chunk)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}python\n{chunk}\n{fence}"


def render_repository_note(
    graph: GraphSnapshot, nodes: dict[str, GraphNode], filenames: dict[str, str]
) -> str:
    """Render the vault entry note with counts and module links."""
    node_counts = {node_type.value: 0 for node_type in NodeType}
    edge_counts = {edge_type.value: 0 for edge_type in EdgeType}
    for node in graph.nodes:
        node_counts[node.node_type.value] += 1
    for edge in graph.edges:
        edge_counts[edge.edge_type.value] += 1
    modules = [node for node in graph.nodes if node.node_type is NodeType.MODULE]
    lines = [
        "# Repository",
        "",
        "**Nodes:** " + str(len(graph.nodes)) + "  ",
        "**Edges:** " + str(len(graph.edges)),
        "",
        "## Node types",
        "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in node_counts.items())
    lines.extend(["", "## Edge types", ""])
    lines.extend(f"- {name}: {count}" for name, count in edge_counts.items())
    lines.extend(["", "## Modules", ""])
    lines.extend(f"- [[{filenames[node.node_id]}]]" for node in modules)
    return "\n".join(lines) + "\n"
