"""DiscoveryGraph nodes: each reuses one existing audit component unchanged."""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from repoagent.ai.provider import LLMProvider, require_provider
from repoagent.analysis.analyzer import RepositoryAnalyzer
from repoagent.application.audit_evidence import attach_evidence
from repoagent.application.audit_verification import verify_candidates
from repoagent.audit.context import AuditContext
from repoagent.audit.dedupe import deduplicate
from repoagent.audit.detectors import Detector, RuffDetector, ast_detectors
from repoagent.audit.detectors import graph_detectors as graph_rules
from repoagent.domain.audit import CandidateIssue
from repoagent.domain.audit_report import AuditMetrics
from repoagent.domain.github import RepositoryHandle
from repoagent.domain.repository import RepositorySpec
from repoagent.graph.builder import RepositoryGraphBuilder
from repoagent.ports.index_store import IndexStore
from repoagent.ports.sandbox import SandboxRunner
from repoagent.retrieval.embeddings import EmbeddingProvider


@dataclass(frozen=True)
class DiscoveryDeps:
    store: IndexStore
    embedding: EmbeddingProvider
    llm: LLMProvider | None
    sandbox_runner: SandboxRunner | None = None
    load: Callable[[str], RepositoryHandle] | None = None


class DiscoveryState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    source: str
    limit: int | None = None
    handle: RepositoryHandle | None = None
    context: AuditContext | None = None
    static_candidates: list[CandidateIssue] = Field(default_factory=list)
    graph_candidates: list[CandidateIssue] = Field(default_factory=list)
    by_source: dict[str, int] = Field(default_factory=dict)
    candidates: list[CandidateIssue] = Field(default_factory=list)
    removed: int = 0
    metrics: AuditMetrics | None = None


def local_handle(source: str) -> RepositoryHandle:
    return RepositoryHandle(source=source, name=Path(source).name, path=source)


class DiscoveryNodes:
    def __init__(self, deps: DiscoveryDeps) -> None:
        self._deps = deps

    def load(self, state: DiscoveryState) -> dict:
        loader = self._deps.load or local_handle
        return {"handle": loader(state.source)}

    def analyze(self, state: DiscoveryState) -> dict:
        spec = RepositorySpec(source=state.handle.path)
        analysis = RepositoryAnalyzer().analyze(spec)
        graph = RepositoryGraphBuilder().build(analysis)
        root = Path(analysis.repository_root)
        return {"context": AuditContext(analysis, root, graph)}

    def _run(self, state: DiscoveryState, detectors: list[Detector]) -> tuple:
        found, by_source = [], dict(state.by_source)
        for detector in detectors:
            hits = detector.detect(state.context)
            found.extend(hits)
            by_source[detector.name] = by_source.get(detector.name, 0) + len(hits)
        return found, by_source

    def static_detectors(self, state: DiscoveryState) -> dict:
        rules = [*ast_detectors(), RuffDetector(self._deps.sandbox_runner)]
        found, by_source = self._run(state, rules)
        return {"static_candidates": found, "by_source": by_source}

    def graph_detectors(self, state: DiscoveryState) -> dict:
        found, by_source = self._run(state, graph_rules())
        return {"graph_candidates": found, "by_source": by_source}

    def deduplicate(self, state: DiscoveryState) -> dict:
        found = [*state.static_candidates, *state.graph_candidates]
        kept, removed = deduplicate(found)
        kept.sort(key=lambda c: -c.confidence)
        if state.limit is not None:
            kept = kept[: state.limit]
        return {"candidates": kept, "removed": removed}

    def enrich(self, state: DiscoveryState) -> dict:
        deps, context = self._deps, state.context
        enriched = attach_evidence(
            deps.store,
            deps.embedding,
            state.handle.path,
            context.root,
            context.graph,
            state.candidates,
        )
        return {"candidates": enriched}

    def verify(self, state: DiscoveryState) -> dict:
        provider = require_provider(self._deps.llm, "audits")
        verified, metrics = verify_candidates(provider, state.candidates)
        generated = len(state.static_candidates) + len(state.graph_candidates)
        metrics = metrics.model_copy(
            update={
                "candidates_generated": generated,
                "candidates_by_source": state.by_source,
                "duplicate_findings_removed": state.removed,
            }
        )
        return {"candidates": verified, "metrics": metrics}
