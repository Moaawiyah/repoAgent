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
        hypotheses, discarded = [], 0
        for draft in drafts.hypotheses:
            cited = [*draft.supporting_evidence_ids, *draft.contradicting_evidence_ids]
            discarded += sum(identifier not in known for identifier in cited)
            contradicting = [i for i in draft.contradicting_evidence_ids if i in known]
            supporting = [
                identifier
                for identifier in draft.supporting_evidence_ids
                if identifier in known
                and known[identifier].relevance == EvidenceRelevance.RELEVANT
            ]
            supported = {known[identifier].qualified_name for identifier in supporting}
            symbols = grounded_symbols(draft.affected_symbols, supported)
            if not supporting or not symbols:
                continue
            confidence = (
                min(draft.confidence, 0.6) if contradicting else draft.confidence
            )
            hypotheses.append(
                RootCauseHypothesis(
                    statement=draft.statement,
                    confidence=confidence,
                    supporting_evidence=supporting,
                    contradicting_evidence=contradicting,
                    affected_symbols=symbols,
                    open_questions=draft.open_questions,
                )
            )
        if discarded and not hypotheses:
            return {**failure(state, "hypothesis_created"), "usage": usage}
        note = f"; discarded {discarded} unknown evidence IDs" if discarded else ""
        return {
            "hypotheses": hypotheses,
            "usage": usage,
            "trace": trace(
                state,
                "hypothesis_created",
                "continue",
                f"{len(hypotheses)} supported hypotheses{note}",
            ),
        }


def grounded_symbols(symbols: list[str], supported: set[str]) -> list[str]:
    """Map each named symbol to the one cited qualified name it denotes.

    Models often shorten names (``ulabel`` for ``idna.core.ulabel``). A name
    counts only if it equals, or is a dotted suffix of, exactly one symbol
    from the cited evidence; anything else stays ungrounded and is dropped.
    """
    grounded: list[str] = []
    for symbol in symbols:
        name = symbol.strip().removesuffix("()")
        matches = [s for s in supported if s == name or s.endswith("." + name)]
        if len(matches) == 1 and matches[0] not in grounded:
            grounded.append(matches[0])
    return grounded
