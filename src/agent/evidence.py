"""Bounded retrieval and source-aware evidence assessment."""

from repoagent.agent.shared import failure, fresh_queries, generate, trace
from repoagent.agent.state import InvestigationState
from repoagent.ai.models import EvidenceAssessment
from repoagent.ai.provider import LLMProvider
from repoagent.domain.errors import LLMError
from repoagent.domain.evidence import EvidenceRelevance
from repoagent.tools.repository import RepositoryToolkit


class EvidenceNodes:
    def __init__(self, provider: LLMProvider, toolkit: RepositoryToolkit) -> None:
        self._provider, self._toolkit = provider, toolkit

    def retrieve(self, state: InvestigationState) -> dict:
        state = state.model_copy(
            update={"current_iteration": state.current_iteration + 1}
        )
        evidence = list(state.evidence)
        known = {e.evidence_id for e in evidence}
        queries = fresh_queries(state, state.pending_queries)
        executed = []
        for query in queries:
            if self._toolkit.calls >= state.limits.max_tool_calls:
                break
            if len(evidence) >= state.limits.max_evidence:
                break
            executed.append(query)
            for item in self._toolkit.search_code(query, state.top_k):
                if (
                    item.evidence_id not in known
                    and len(evidence) < state.limits.max_evidence
                ):
                    known.add(item.evidence_id)
                    evidence.append(item)
        return {
            "current_iteration": state.current_iteration,
            "executed_queries": [*state.executed_queries, *executed],
            "pending_queries": [],
            "evidence": evidence,
            "tool_calls": self._toolkit.calls,
            "trace": trace(
                state,
                "retrieve",
                "continue",
                query="; ".join(executed),
                symbols=[e.qualified_name for e in evidence],
            ),
        }

    def assess_evidence(self, state: InvestigationState) -> dict:
        try:
            assessment, usage = generate(
                state, self._provider, "evidence_assessment", EvidenceAssessment
            )
        except LLMError as error:
            return failure(state, "evidence_assessed", str(error))
        known = {e.evidence_id for e in state.evidence}
        # Citations of unknown IDs are discarded, never attached to evidence;
        # the stage fails only when no assessment references supplied evidence.
        valid = [a for a in assessment.assessments if a.evidence_id in known]
        discarded = len(assessment.assessments) - len(valid)
        if assessment.assessments and not valid:
            return {**failure(state, "evidence_assessed"), "usage": usage}
        verdicts = {a.evidence_id: a for a in valid}
        items = []
        for item in state.evidence:
            verdict = verdicts.get(item.evidence_id)
            if verdict:
                item = item.model_copy(
                    update={
                        "relevance": EvidenceRelevance(verdict.relevance),
                        "reason": verdict.reason,
                        "confidence": 0.0,
                    }
                )
            items.append(item)
        supported = any(e.relevance == EvidenceRelevance.RELEVANT for e in items)
        return {
            "evidence": items,
            "usage": usage,
            "enough_evidence": assessment.enough_evidence and supported,
            "next_queries": fresh_queries(state, assessment.next_queries),
            "trace": trace(
                state,
                "evidence_assessed",
                "enough" if supported and assessment.enough_evidence else "need_more",
                "; ".join(
                    [*assessment.unknowns]
                    + (
                        [f"discarded {discarded} unknown evidence IDs"]
                        if discarded
                        else []
                    )
                ),
            ),
        }
