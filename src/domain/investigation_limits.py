"""Investigation resource policy."""

from pydantic import Field

from repoagent.analysis.models import AnalysisModel


class InvestigationLimits(AnalysisModel):
    """Hard bounds that keep investigations finite and cheap."""

    max_iterations: int = Field(default=3, ge=1, le=10)
    max_queries: int = Field(default=8, ge=1, le=20)
    max_evidence: int = Field(default=12, ge=1, le=30)
    max_tool_calls: int = Field(default=30, ge=1, le=100)
    context_chars: int = Field(default=12000, ge=1000, le=16000)
