"""Readable CLI presentation for indexing, search, evaluation, and graphs."""

from repoagent.evaluation.models import EvaluationReport
from repoagent.export.obsidian import ExportSummary
from repoagent.graph.models import GraphInspection, GraphSummary
from repoagent.retrieval.models import SearchResponse
from repoagent.retrieval.persistence import IndexSummary


def render_index(summary: IndexSummary) -> str:
    """Render an indexing summary."""
    return "\n".join(
        [
            "RepoAgent Repository Index",
            "",
            f"Repository: {summary.repository_name}",
            f"Repository ID: {summary.repository_id}",
            f"Python files: {summary.python_files}",
            f"Chunks: {summary.chunk_count}",
            "Embeddings: "
            f"{summary.embedding_provider} ({summary.embedding_dimension} dims)",
        ]
    )


def render_search(response: SearchResponse) -> str:
    """Render ranked hits with provenance and a one-line preview."""
    strategy = response.strategy.value
    if response.reranked:
        strategy += " (reranked)"
    lines = [
        "RepoAgent Search Results",
        "",
        f"Query: {response.query}",
        f"Strategy: {strategy}",
        "",
    ]
    if not response.results:
        lines.append("No matching code found.")
    for result in response.results:
        chunk = result.chunk
        lines.append(
            f"{result.rank}. {chunk.file_path} - {chunk.qualified_name}"
            f" (lines {chunk.start_line}-{chunk.end_line})"
            f" [{result.source.value}] score {result.score:.4f}"
        )
        source_lines = chunk.source.splitlines()
        preview = source_lines[0].strip()[:88] if source_lines else ""
        lines.append(f"   {preview}")
    return "\n".join(lines)


def render_graph_summary(summary: GraphSummary) -> str:
    """Render node/edge counts for the repository graph."""
    lines = [
        "RepoAgent Repository Graph",
        "",
        f"Repository: {summary.repository}",
        f"Nodes: {summary.node_count}",
        f"Edges: {summary.edge_count}",
        "",
        "Node types:",
    ]
    lines.extend(
        f"- {name}: {count}" for name, count in sorted(summary.nodes_by_type.items())
    )
    lines.append("Edge types:")
    lines.extend(
        f"- {name}: {count}" for name, count in sorted(summary.edges_by_type.items())
    )
    return "\n".join(lines)


def render_graph_inspection(inspection: GraphInspection) -> str:
    """Render the neighborhood of one symbol."""
    lines = [inspection.symbol]
    for title, edges, arrow in (
        ("Outgoing", inspection.outgoing, "→"),
        ("Incoming", inspection.incoming, "←"),
        ("Parent", inspection.parents, "←"),
    ):
        if not edges:
            continue
        lines.append(f"{title}:")
        for edge in edges:
            target = edge.target if arrow == "→" else edge.source
            lines.append(f"{edge.edge_type.value.upper()} {arrow} {target}")
    return "\n".join(lines)


def render_export(summary: ExportSummary) -> str:
    """Render an Obsidian export summary."""
    return "\n".join(
        [
            "RepoAgent Obsidian Export",
            "",
            f"Destination: {summary.destination}",
            f"Notes: {summary.notes}",
            f"Links: {summary.links}",
            f"Edges: {summary.edge_count}",
        ]
    )


def render_evaluation(report: EvaluationReport) -> str:
    """Render the strategy comparison table."""
    lines = [
        "RepoAgent Retrieval Evaluation",
        "",
        f"Repository: {report.repository}",
        f"K: {report.k}",
        "",
        f"{'Strategy':<10}{'Queries':>8}{'Recall@K':>10}{'MRR':>8}"
        f"{'Hit@K':>8}{'Prec@K':>8}",
    ]
    for row in report.rows:
        lines.append(
            f"{row.strategy.value:<10}{row.queries:>8}{row.recall_at_k:>10.3f}"
            f"{row.mrr:>8.3f}{row.hit_rate_at_k:>8.3f}{row.precision_at_k:>8.3f}"
        )
    return "\n".join(lines)
