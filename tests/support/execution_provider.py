"""Deterministic provider for M7 loops: patch sequence plus failure analyses."""

import json

from repoagent import RepoAgent, Settings
from repoagent.ai.provider import CompletionResult
from tests.support.repair_provider import DIFF, RepairProvider

DIFF2 = DIFF.replace(
    'user["email"].lower() == email.lower()',
    'user["email"].casefold() == email.casefold()',
)
DIFF3 = DIFF.replace(".lower()", ".strip().lower()")
ISSUE = "Users with uppercase email addresses cannot log in"


def analysis(action="revise_patch", caused=False, uncertain=False, **extra):
    return {
        "category": "test_failure",
        "likely_reason": "patch missed normalization in secondary lookup",
        "affected_file": "app/users/repository.py",
        "patch_caused_failure": caused,
        "root_cause_uncertain": uncertain,
        "next_action": action,
        **extra,
    }


class ExecutionProvider(RepairProvider):
    def __init__(self, patches=(DIFF, DIFF2, DIFF3), analyses=(), **kwargs):
        super().__init__(**kwargs)
        self._patches, self._analyses = list(patches), list(analyses or [analysis()])
        self._proposals = self._failures = 0

    def prompts(self, name):
        return [r for r in self.requests if r.prompt_name == name]

    def complete(self, request):
        if request.prompt_name == "patch_proposal":
            self._patch = self._patches[min(self._proposals, len(self._patches) - 1)]
            self._proposals += 1
        if request.prompt_name != "failure_analysis":
            return super().complete(request)
        self.requests.append(request)
        result = self._analyses[min(self._failures, len(self._analyses) - 1)]
        self._failures += 1
        return CompletionResult(text=json.dumps(result), model=self.name)


def run_repair(tmp_path, root, runner, provider, **kwargs):
    client = RepoAgent(
        settings=Settings(data_dir=tmp_path / "data"), sandbox_runner=runner
    )
    client.index(root)
    return client.repair_and_validate(root, ISSUE, provider=provider, **kwargs)
