"""Hypotheses survive sloppy citations only when still grounded in evidence."""

import json

from repoagent.agent.reasoning import grounded_symbols
from repoagent.ai.provider import CompletionResult
from tests.support.providers import FixtureProvider
from tests.unit.test_investigation_challenges import run


def test_grounded_symbols_resolve_unique_suffixes_only():
    supported = {"pkg.a.load", "pkg.b.load", "pkg.core.ulabel"}
    assert grounded_symbols(["ulabel", "core.ulabel()", "load", "x"], supported) == [
        "pkg.core.ulabel"
    ]
    assert grounded_symbols(["pkg.a.load"], supported) == ["pkg.a.load"]


def test_mistyped_citation_and_short_symbol_keep_a_grounded_hypothesis(tmp_path):
    class Sloppy(FixtureProvider):
        def complete(self, request):
            result = super().complete(request)
            if request.prompt_name == "hypothesis_set":
                payload = json.loads(result.text)
                draft = payload["hypotheses"][0]
                draft["supporting_evidence_ids"].append("ffffffffffffffff")
                draft["affected_symbols"] = ["find_by_email()", "invented.name"]
                return CompletionResult(text=json.dumps(payload))
            return result

    report = run(tmp_path, Sloppy())
    assert report.termination_reason == "confident_root_cause"
    assert report.primary_hypothesis.affected_symbols == [
        "app.users.repository.UserRepository.find_by_email"
    ]
    assert "ffffffffffffffff" not in report.primary_hypothesis.supporting_evidence
    assert any("discarded 1 unknown" in t.rationale for t in report.trace)
