"""Mermaid diagrams drawn from the real compiled LangGraph workflows.

Graphs are built with inert dependencies: compiling never calls a node, so
no provider, index, or sandbox is needed and the diagrams cannot drift
from the code that runs.
"""

from typing import Any, cast

from repoagent.agent.execution_agent import ExecutionRepairAgent
from repoagent.agent.execution_state import RepairLoopLimits
from repoagent.agent.investigator import InvestigatorAgent
from repoagent.agent.repair_agent import RepairAgent
from repoagent.workflows.discovery_graph import DiscoveryGraph
from repoagent.workflows.discovery_nodes import DiscoveryDeps
from repoagent.workflows.repair_graph import RepairGraph, RepairPorts

_INERT = cast(Any, None)


def compiled_workflows() -> dict[str, Any]:
    """Every LangGraph workflow by name, top-level workflows first."""
    ports = RepairPorts(load=_INERT, index=_INERT, repair=_INERT)
    return {
        "repair_workflow": RepairGraph(ports).graph,
        "discovery_workflow": DiscoveryGraph(DiscoveryDeps(_INERT, _INERT, None)).graph,
        "investigator": InvestigatorAgent(_INERT, _INERT).graph,
        "patch_review": RepairAgent(".", _INERT, max_revisions=0).graph,
        "sandbox_repair": ExecutionRepairAgent(
            _INERT, _INERT, _INERT, RepairLoopLimits()
        ).graph,
    }


def workflow_diagrams(name: str | None = None) -> dict[str, str]:
    """Mermaid source per workflow; ``name`` selects a single one."""
    graphs = compiled_workflows()
    if name is not None and name not in graphs:
        raise ValueError(f"Unknown workflow: {name}; expected one of {sorted(graphs)}")
    selected = {name: graphs[name]} if name else graphs
    return {key: graph.get_graph().draw_mermaid() for key, graph in selected.items()}
