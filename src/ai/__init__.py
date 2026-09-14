"""Language-model boundary: provider protocol, models, adapters (M5)."""

from repoagent.ai.models import (
    AIModel,
    AssessedEvidence,
    EvaluationVerdict,
    EvidenceAssessment,
    HypothesisDraft,
    HypothesisEvaluation,
    HypothesisSet,
    InvestigationDecision,
    IssueAnalysis,
    SearchPlan,
)
from repoagent.ai.openai_provider import OpenAIChatProvider, llm_provider_from_settings
from repoagent.ai.provider import (
    CompletionRequest,
    CompletionResult,
    CompletionUsage,
    LLMProvider,
    require_provider,
)
from repoagent.ai.structured import structured_generate

__all__ = [
    "AIModel",
    "AssessedEvidence",
    "CompletionRequest",
    "CompletionResult",
    "CompletionUsage",
    "EvidenceAssessment",
    "EvaluationVerdict",
    "HypothesisDraft",
    "HypothesisEvaluation",
    "HypothesisSet",
    "InvestigationDecision",
    "IssueAnalysis",
    "LLMProvider",
    "OpenAIChatProvider",
    "SearchPlan",
    "llm_provider_from_settings",
    "require_provider",
    "structured_generate",
]
