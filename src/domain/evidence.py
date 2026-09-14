"""Evidence item models with full repository provenance."""

from enum import StrEnum

from pydantic import Field

from repoagent.analysis.models import AnalysisModel
from repoagent.retrieval.models import GraphHop

MAX_SNIPPET_CHARS = 2000


class EvidenceRelevance(StrEnum):
    """Assessed relevance of retrieved code to the issue."""

    RELEVANT = "relevant"
    PARTIALLY_RELEVANT = "partially_relevant"
    IRRELEVANT = "irrelevant"


class EvidenceItem(AnalysisModel):
    """Retrieved code treated as evidence with full provenance."""

    repository_id: str = ""
    chunk_id: str = ""
    evidence_id: str
    query: str
    retrieval_source: str
    file_path: str
    symbol_name: str
    qualified_name: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    snippet: str = Field(max_length=MAX_SNIPPET_CHARS * 2)
    rank: int
    relevance: EvidenceRelevance | None = None
    reason: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    graph_path: list[GraphHop] = Field(default_factory=list)
