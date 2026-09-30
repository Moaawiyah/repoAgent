"""Map LangGraph node starts onto user-facing workflow stages.

Node starts come from LangGraph's ``tasks`` stream (see
``agent.graph_runtime``), which includes graphs invoked inside a node, so
the existing Investigator, Developer/Reviewer and sandbox repair subgraphs
are observed without modifying them.
"""

from collections.abc import Callable, Mapping

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


def node_stage_reporter(
    nodes: Mapping[str, str], sink: StageSink
) -> Callable[[str], None]:
    """Report each mapped node start as a running stage; others are ignored."""

    def report(node: str) -> None:
        key = nodes.get(node)
        if key is not None:
            sink(key, StageStatus.RUNNING, "")

    return report
