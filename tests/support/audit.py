"""Shared helper for building an AuditContext over the audit test fixture."""

from pathlib import Path

from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.audit.context import AuditContext
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "audit_repo"


def build_context(root: Path = FIXTURE) -> AuditContext:
    analysis = RepositoryAnalyzer().analyze(RepositorySpec(source=str(root)))
    store = RepositoryGraphBuilder().build(analysis)
    return AuditContext(analysis, root.resolve(), store)
