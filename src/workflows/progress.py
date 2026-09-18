"""LangChain callback bridge from LangGraph node execution to workflow stages.

LangGraph propagates run callbacks into graphs invoked inside a node, so
one handler observes the existing Investigator, Developer/Reviewer and
sandbox repair subgraphs without modifying them. Only the node run itself
(``name == langgraph_node``) is reported, never inner runnables.
"""

from collections.abc import Callable, Mapping
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from repoagent.domain.workflow import StageStatus

StageSink = Callable[[str, StageStatus, str], None]


def ignore_stage(key: str, status: StageStatus, detail: str = "") -> None:
    """Default sink for callers that do not observe progress."""


# Node names of the existing subgraphs (agent/*) → user-facing stage keys.
REPAIR_NODE_STAGES: Mapping[str, str] = {
    "analyze_issue": "investigator",
    "plan_search": "investigator",
    "retrieve": "retrieval",
    "assess_evidence": "investigator",
    "hypothesize": "investigator",
    "evaluate": "investigator",
    "refine": "retrieval",
    "develop": "developer",
    "validate": "static_validation",
    "review": "reviewer",
    "baseline": "docker_validation",
    "execute": "docker_validation",
    "analyze": "failure_analysis",
    "reinvestigate": "investigator",
}


class WorkflowProgressHandler(BaseCallbackHandler):
    """Reports each mapped LangGraph node start as a running stage."""

    def __init__(self, nodes: Mapping[str, str], sink: StageSink) -> None:
        self._nodes, self._sink = nodes, sink

    def on_chain_start(
        self,
        serialized: dict[str, Any] | None,
        inputs: dict[str, Any] | Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        node = (metadata or {}).get("langgraph_node")
        if node is None or kwargs.get("name") != node:
            return
        key = self._nodes.get(node)
        if key is not None:
            self._sink(key, StageStatus.RUNNING, "")
