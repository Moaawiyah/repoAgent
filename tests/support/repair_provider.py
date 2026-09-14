"""Deterministic M5/M6 provider used only by repair workflow tests."""

import json

from repoagent.ai.provider import CompletionResult
from tests.support.providers import FixtureProvider

DIFF = """--- a/app/users/repository.py
+++ b/app/users/repository.py
@@ -1,1 +1,1 @@
-            if user["email"] == email:
+            if user["email"].lower() == email.lower():
"""


class RepairProvider(FixtureProvider):
    """Supplies minimal valid patch/review outputs after M5 stages."""

    def __init__(self, decisions=("approve",), patch=DIFF, **kwargs) -> None:
        super().__init__(**kwargs)
        self._decisions, self._patch, self._review = list(decisions), patch, 0

    def complete(self, request):
        if request.prompt_name == "patch_proposal":
            result = {
                "plan": {
                    "summary": "Normalize both values before email comparison.",
                    "affected_files": ["app/users/repository.py"],
                    "affected_symbols": [
                        "app.users.repository.UserRepository.find_by_email"
                    ],
                    "recommended_tests": ["uppercase email login"],
                },
                "unified_diff": self._patch,
            }
        elif request.prompt_name == "patch_review":
            decision = self._decisions[min(self._review, len(self._decisions) - 1)]
            self._review += 1
            result = {
                "decision": decision,
                "rationale": "Fixture reviewer decision.",
                "recommended_tests": ["uppercase email login"],
            }
        else:
            return super().complete(request)
        self.requests.append(request)
        return CompletionResult(text=json.dumps(result), model=self.name)
