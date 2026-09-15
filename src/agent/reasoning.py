"""Root-cause hypotheses must cite assessed repository evidence explicitly."""

from repoagent.agent.shared import failure, generate, trace
from repoagent.agent.state import InvestigationState
from repoagent.ai.models import HypothesisSet
from repoagent.ai.provider import LLMProvider
from repoagent.domain.errors import LLMError
from repoagent.domain.evidence import EvidenceRelevance
from repoagent.domain.investigation import RootCauseHypothesis


class ReasoningNodes:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def hypothesize(self, state: InvestigationState) -> dict:
        try:
            drafts, usage = generate(
                state, self._provider, "hypothesis_set", HypothesisSet
            )
        except LLMError as error:
            return failure(state, "hypothesis_created", str(error))
        known = {e.evidence_id: e for e in state.evidence}
        hypotheses = []
        for draft in drafts.hypotheses:
            cited = [*draft.supporting_evidence_ids, *draft.contradicting_evidence_ids]
            if any(identifier not in known for identifier in cited):
                return {**failure(state, "hypothesis_created"), "usage": usage}
            supporting = [
                identifier
                for identifier in draft.supporting_evidence_ids
                if known[identifier].relevance == EvidenceRelevance.RELEVANT
            ]
            if not supporting:
                continue
            supported_symbols = {
                known[identifier].qualified_name for identifier in supporting
            }
            if (
                not draft.affected_symbols
                or not set(draft.affected_symbols) <= supported_symbols
            ):
                continue
            confidence = (
                min(draft.confidence, 0.6)
                if draft.contradicting_evidence_ids
                else draft.confidence
            )
            hypotheses.append(
                RootCauseHypothesis(
                    statement=draft.statement,
                    confidence=confidence,
                    supporting_evidence=supporting,
                    contradicting_evidence=draft.contradicting_evidence_ids,
                    affected_symbols=draft.affected_symbols,
                    open_questions=draft.open_questions,
                )
            )
        return {
            "hypotheses": hypotheses,
            "usage": usage,
            "trace": trace(
                state,
                "hypothesis_created",
                "continue",
                f"{len(hypotheses)} supported hypotheses",
            ),
        }
