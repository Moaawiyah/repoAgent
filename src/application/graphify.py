"""Graphify workflow: one graph build feeding graph.json and/or Obsidian.

Reuses the M2 analyzer, the M4 ``RepositoryGraphBuilder``, and the existing
``ObsidianExporter`` — this service only orchestrates them so a single
static-analysis pass and a single graph build serve both outputs.
"""

import logging
from pathlib import Path

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.domain.repository import RepositorySpec
from repoagent.export.obsidian import ObsidianExporter
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.graph.serializer import (
    GraphifyResult,
    build_document,
    write_graph_json,
)

LOGGER = logging.getLogger(__name__)


class GraphifyService:
    """Builds the repository graph once and persists the requested outputs."""

    def __init__(self, analyzer: RepositoryAnalyzer | None = None) -> None:
        self._analyzer = analyzer or RepositoryAnalyzer()

    def run(
        self,
        spec: RepositorySpec,
        *,
        output: Path | None = None,
        obsidian: Path | None = None,
        artifacts_dir: Path | None = None,
        overwrite: bool = False,
    ) -> GraphifyResult:
        """Analyze, build the graph once, and write the requested outputs.

        ``artifacts_dir``, when given, fills in ``output``/``obsidian`` that
        were left unset as ``<artifacts_dir>/<repository_name>/graph.json``
        and ``.../vault`` — one subdirectory per repository, keyed by the
        name M2 analysis assigns it, so repeated runs never collide.
        """
        analysis = self._analyzer.analyze(spec)
        if artifacts_dir is not None:
            repo_dir = artifacts_dir / analysis.repository_name
            output = output or repo_dir / "graph.json"
            obsidian = obsidian or repo_dir / "vault"
        snapshot = RepositoryGraphBuilder().build(analysis).to_snapshot()
        symbols = len(analysis.symbols)
        LOGGER.info(
            "Graphify build completed",
            extra={
                "event": "graphify_built",
                "repository": analysis.repository_name,
            },
        )
        if output is not None:
            document = build_document(
                snapshot,
                repository=analysis.repository_name,
                files=analysis.python_files,
                symbols=symbols,
            )
            write_graph_json(document, output)
            LOGGER.info("graph.json written", extra={"event": "graph_json_written"})
        if obsidian is not None:
            ObsidianExporter(Path(analysis.repository_root)).export(
                snapshot, obsidian, overwrite=overwrite
            )
            LOGGER.info("Obsidian vault written", extra={"event": "obsidian_written"})
        return GraphifyResult(
            repository=analysis.repository_name,
            files=analysis.python_files,
            symbols=symbols,
            node_count=len(snapshot.nodes),
            edge_count=len(snapshot.edges),
            graph_json_path=str(output) if output is not None else None,
            obsidian_path=str(obsidian) if obsidian is not None else None,
        )
