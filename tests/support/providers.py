"""Deterministic fixture provider: routing test data, NOT an AI benchmark model."""

import json

from repoagent.ai.provider import CompletionResult


class FixtureProvider:
    name = "fixture-scripted"

    def __init__(self, rounds=1, weak=False, multiple=False):
        self.requests = []
        self.rounds, self.weak, self.multiple = rounds, weak, multiple

    def complete(self, request):
        self.requests.append(request)
        data = json.loads(request.user)["untrusted_data"]
        evidence = data["evidence"]
        stage = request.prompt_name
        if stage == "issue_analysis":
            result = {
                "concepts": ["email", "lookup"],
                "likely_subsystem": "authentication",
            }
        elif stage == "search_plan":
            result = {"queries": ["email login lookup"]}
        elif stage == "evidence_assessment":
            result = {
                "assessments": [
                    {
                        "evidence_id": e["evidence_id"],
                        "relevance": "relevant",
                        "reason": "Fixture assertion",
                    }
                    for e in evidence
                ],
                "enough_evidence": data["iteration"] >= self.rounds and not self.weak,
                "next_queries": [
                    f"email lookup comparison iteration {data['iteration']}"
                ]
                if data["iteration"] < self.rounds
                else [],
            }
        elif stage == "hypothesis_set":
            selected = sorted(
                evidence, key=lambda e: "find_by_email" not in e["qualified_name"]
            )
            selected = selected[: 2 if self.multiple else 1]
            result = {
                "hypotheses": [
                    {
                        "statement": "Fixture: raw email equality lookup",
                        "confidence": 0.8,
                        "supporting_evidence_ids": [e["evidence_id"]],
                        "affected_symbols": [e["qualified_name"]],
                    }
                    for e in selected
                ]
            }
            if self.multiple and len(result["hypotheses"]) > 1:
                result["hypotheses"][1]["statement"] = "Fixture: caller normalization"
        else:
            hypotheses = data["hypotheses"]
            result = {
                "enough_confidence": not self.weak,
                "primary_hypothesis_id": hypotheses[0]["hypothesis_id"]
                if hypotheses
                else None,
                "evaluations": [
                    {
                        "hypothesis_id": h["hypothesis_id"],
                        "confidence": 0.4 if self.weak else 0.8 - i * 0.1,
                        "verdict": "weakened" if self.weak else "strengthened",
                    }
                    for i, h in enumerate(hypotheses)
                ],
                "next_queries": [],
            }
        return CompletionResult(text=json.dumps(result), model=self.name)
