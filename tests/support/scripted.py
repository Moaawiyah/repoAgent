"""Scripted deterministic provider for precise workflow tests."""

import json

from repoagent.ai.provider import (
    CompletionRequest,
    CompletionResult,
)


class ScriptedLLMProvider:
    """Returns queued responses; records every request for assertions."""

    name = "scripted"

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.requests: list[CompletionRequest] = []

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.requests.append(request)
        if not self._responses:
            raise AssertionError("Scripted provider ran out of responses")
        payload = self._responses.pop(0)
        payload = payload(request) if callable(payload) else payload
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return CompletionResult(text=text, model=self.name)
