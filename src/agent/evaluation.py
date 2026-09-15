"""Challenge hypotheses; confidence never overrides provenance checks."""

from repoagent.agent.shared import failure, fresh_queries, generate, trace
from repoagent.agent.state import InvestigationState
from repoagent.ai.models import EvaluationVerdict, InvestigationDecision
from repoagent.ai.provider import LLMProvider
from repoagent.domain.errors import LLMError
from repoagent.domain.investigation import HypothesisStatus


class EvaluationNode:
    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def evaluate(self, state: InvestigationState) -> dict:
        try:
            decision, usage = generate(
                state, self._provider, "investigation_decision", InvestigationDecision
            )
        except LLMError as error:
            return failure(state, "hypothesis_evaluated", str(error))
        known = {h.hypothesis_id for h in state.hypotheses}
        if any(e.hypothesis_id not in known for e in decision.evaluations) or (
            decision.primary_hypothesis_id is not None
            and decision.primary_hypothesis_id not in known
        ):
            return {**failure(state, "hypothesis_evaluated"), "usage": usage}
        verdicts = {e.hypothesis_id: e for e in decision.evaluations}
        hypotheses = []
        for hypothesis in state.hypotheses:
            verdict = verdicts.get(hypothesis.hypothesis_id)
            confidence = min(hypothesis.confidence, 0.6)
            status = hypothesis.status
            if verdict:
                confidence = verdict.confidence
                status = HypothesisStatus.EVALUATED
                if verdict.verdict != EvaluationVerdict.STRENGTHENED:
                    confidence = min(confidence, 0.6)
            if hypothesis.contradicting_evidence:
                confidence = min(confidence, 0.6)
            hypotheses.append(
                hypothesis.model_copy(
                    update={"confidence": confidence, "status": status}
                )
            )
        ranked = sorted(hypotheses, key=lambda h: (-h.confidence, h.hypothesis_id))
        primary = next(
            (h for h in ranked if h.hypothesis_id == decision.primary_hypothesis_id),
            None,
        )
        primary = primary or (ranked[0] if ranked else None)
        confident = bool(
            primary
            and state.enough_evidence
            and decision.enough_confidence
            and primary.confidence >= 0.75
            and primary.status == HypothesisStatus.EVALUATED
        )
        return {
            "hypotheses": ranked,
            "primary_hypothesis_id": primary.hypothesis_id if primary else None,
            "confidence": primary.confidence if primary else 0.0,
            "termination": "confident_root_cause" if confident else None,
            "next_queries": fresh_queries(state, decision.next_queries),
            "usage": usage,
            "trace": trace(
                state,
                "hypothesis_evaluated",
                "confident" if confident else "weak",
                "; ".join(e.notes for e in decision.evaluations),
            ),
        }
