"""LLM Failure Analyzer invoked only when deterministic triage is insufficient."""

import json

from repoagent.agent.repair_context import SYSTEM
from repoagent.ai.failure_models import FailureAnalyzerOutput
from repoagent.ai.provider import LLMProvider
from repoagent.ai.structured import structured_generate
from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import PatchProposal
from repoagent.domain.repair_execution import FailureAnalysis, NextAction, RepairAttempt
from repoagent.domain.validation import ValidationResult

MAX_DIFF_CHARS, MAX_OUTPUT_CHARS, MAX_EVIDENCE = 6000, 2000, 4
ANALYZER_RULES = (
    " As Failure Analyzer, diagnose why sandbox validation failed. Choose "
    "reinvestigate only when the evidence shows the root-cause hypothesis is wrong."
)


def failure_context(
    report: InvestigationReport,
    proposal: PatchProposal,
    validation: ValidationResult,
    attempts: list[RepairAttempt],
) -> str:
    """Focused payload: failing tests, bounded output, touched-file evidence."""
    files = set(proposal.plan.affected_files)
    evidence = [
        {
            "file": item.file_path,
            "symbol": item.qualified_name,
            "lines": [item.start_line, item.end_line],
            "snippet": item.snippet[:800],
        }
        for item in report.evidence
        if item.relevance and item.file_path in files
    ][:MAX_EVIDENCE]
    tests = validation.tests
    pytest_output = next(
        (c.stdout for c in validation.execution.commands if c.kind == "pytest"), ""
    )
    root = report.primary_hypothesis
    payload = {
        "issue": report.issue.description[:1500],
        "root_cause": root.statement if root else None,
        "patch": {
            "summary": proposal.plan.summary,
            "diff": proposal.unified_diff[:MAX_DIFF_CHARS],
        },
        "evidence": evidence,
        "validation": {
            "summary": validation.summary,
            "comparison": validation.comparison.model_dump(mode="json")
            if validation.comparison
            else None,
            "failed_tests": [f.model_dump(mode="json") for f in tests.failures[:8]]
            if tests
            else [],
            "output_tail": pytest_output[-MAX_OUTPUT_CHARS:],
        },
        "previous_attempts": [
            {
                "attempt": item.number,
                "category": item.failure_analysis.category.value,
                "reason": item.failure_analysis.likely_reason[:200],
            }
            for item in attempts[-3:]
            if item.failure_analysis
        ],
    }
    return json.dumps({"untrusted_data": payload})


class FailureAnalyzerAgent:
    """Produces a structured diagnosis; deterministic facts override the model."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def analyze(
        self,
        report: InvestigationReport,
        proposal: PatchProposal,
        validation: ValidationResult,
        attempts: list[RepairAttempt],
    ) -> FailureAnalysis:
        _, output = structured_generate(
            self._provider,
            "failure_analysis",
            SYSTEM + ANALYZER_RULES,
            failure_context(report, proposal, validation, attempts),
            FailureAnalyzerOutput,
        )
        comparison = validation.comparison
        caused = output.patch_caused_failure or bool(
            comparison and comparison.new_failures
        )
        action = output.next_action
        if output.root_cause_uncertain and action == NextAction.REVISE_PATCH:
            action = NextAction.REINVESTIGATE
        return FailureAnalysis(
            category=output.category,
            likely_reason=output.likely_reason,
            affected_file=output.affected_file,
            affected_symbol=output.affected_symbol,
            patch_caused_failure=caused,
            next_action=action,
            evidence_needed=list(output.evidence_needed),
            source="llm",
        )
