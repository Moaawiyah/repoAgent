"""Callback progress across nested LangGraphs, stage outcomes, graph view."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from repoagent.domain.investigation import InvestigationReport
from repoagent.domain.repair import RepairReport, RepairStatus
from repoagent.domain.repair_execution import (
    ExecutionStatus,
    RepairMetrics,
    ValidatedRepairReport,
)
from repoagent.domain.workflow import StageStatus
from repoagent.graph.models import GraphEdge, GraphNode, GraphSnapshot, NodeType
from repoagent.graph.view import build_view
from repoagent.workflows.outcomes import CURRENT, repair_outcomes
from repoagent.workflows.progress import WorkflowProgressHandler, ignore_stage
from tests.support.execution_provider import ISSUE


class State(TypedDict):
    n: int


def chain(*names, inner=None):
    graph = StateGraph(State)
    previous = START
    for name in names:
        nested = inner and name == "repair"
        action = (lambda s: inner.invoke(s)) if nested else (lambda s: s)
        graph.add_node(name, action)
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    return graph.compile()


def test_handler_reports_nested_subgraph_nodes_once():
    events = []
    inner = chain("develop", "review", "unmapped")
    outer = chain("load_repository", "repair", inner=inner)
    handler = WorkflowProgressHandler(
        {"load_repository": "repository", "develop": "developer", "review": "reviewer"},
        lambda key, status, detail: events.append((key, status)),
    )
    outer.invoke({"n": 1}, config={"callbacks": [handler]})
    assert events == [
        ("repository", StageStatus.RUNNING),
        ("developer", StageStatus.RUNNING),
        ("reviewer", StageStatus.RUNNING),
    ]
    assert ignore_stage("x", StageStatus.DONE) is None


def validated(status, error=None):
    metrics = RepairMetrics(final_status=status)
    return ValidatedRepairReport(
        task_id="t", repository="r", status=status, metrics=metrics, error=error
    )


def test_outcomes_never_upgrade_failures():
    assert repair_outcomes(validated(ExecutionStatus.VALIDATED))[0][:2] == (
        "docker_validation",
        StageStatus.DONE,
    )
    assert repair_outcomes(validated(ExecutionStatus.REVIEW_REJECTED))[0][:2] == (
        "reviewer",
        StageStatus.FAILED,
    )
    key, status, detail = repair_outcomes(
        validated(ExecutionStatus.PROVIDER_ERROR, "LLM call limit reached")
    )[0]
    assert (key, status, detail) == (
        CURRENT,
        StageStatus.FAILED,
        "LLM call limit reached",
    )


def static(status):
    report = InvestigationReport.model_construct(repository="r", issue=ISSUE)
    return RepairReport.model_construct(investigation=report, status=status)


def test_static_outcomes():
    assert repair_outcomes(static(RepairStatus.REJECTED))[0][:2] == (
        "reviewer",
        StageStatus.FAILED,
    )
    approved = repair_outcomes(static(RepairStatus.APPROVED_FOR_RUNTIME_VALIDATION))
    assert approved[0][:2] == ("docker_validation", StageStatus.SKIPPED)


def node(node_id, kind, file="a.py"):
    return GraphNode(
        node_id=node_id,
        node_type=kind,
        name=node_id.split(".")[-1],
        file_path=file,
        start_line=1,
        end_line=2,
        module="a",
    )


def test_graph_view_keeps_focus_first_and_drops_dangling_edges():
    snapshot = GraphSnapshot(
        nodes=[
            node("a", NodeType.MODULE),
            node("a.f", NodeType.FUNCTION),
            node("a.C.m", NodeType.METHOD, file="focus.py"),
            node("a.C", NodeType.CLASS),
        ],
        edges=[
            GraphEdge(source="a", target="a.f", edge_type="defines"),
            GraphEdge(source="a.f", target="a.C.m", edge_type="calls"),
            GraphEdge(source="a.f", target="missing", edge_type="calls"),
        ],
    )
    view = build_view(snapshot, "repo", focus={"focus.py"}, max_nodes=2)
    assert [n.id for n in view.nodes] == ["a", "a.C.m"]
    assert [n.focus for n in view.nodes] == [False, True]
    assert view.edges == [] and view.truncated and view.total_nodes == 4
    full = build_view(snapshot, "repo")
    assert len(full.edges) == 2 and not full.truncated
    assert {n.kind for n in full.nodes} == set(NodeType)
