"""Readable CLI presentation for the graphify command."""

from repoagent.graph.serializer import GraphifyResult


def render_graphify(result: GraphifyResult) -> str:
    """Render a Graphify run summary, matching the spec's plain layout."""
    lines = [
        "Graphify complete",
        "",
        f"Files:          {result.files}",
        f"Symbols:        {result.symbols}",
        f"Nodes:          {result.node_count}",
        f"Relationships:  {result.edge_count}",
    ]
    if result.graph_json_path or result.obsidian_path:
        lines.append("")
    if result.graph_json_path:
        lines.append(f"graph.json: {result.graph_json_path}")
    if result.obsidian_path:
        lines.append(f"Obsidian:   {result.obsidian_path}")
    return "\n".join(lines)
