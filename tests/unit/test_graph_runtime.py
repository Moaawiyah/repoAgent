"""Bounded LangGraph invocation and diagrams drawn from the compiled graphs."""

import json
from typing import TypedDict

import pytest
from langgraph.graph import END, START, StateGraph
from typer.testing import CliRunner

from repoagent.agent.graph_runtime import invoke_bounded
from repoagent.cli.main import app
from repoagent.domain.errors import RepoAgentError, WorkflowLimitError
from repoagent.workflows.diagrams import workflow_diagrams

WORKFLOWS = {
    "repair_workflow",
    "discovery_workflow",
    "investigator",
    "patch_review",
    "sandbox_repair",
}


class Count(TypedDict):
    n: int


def counter(stop_at: int | None):
    graph = StateGraph(Count)
    graph.add_node("step", lambda state: {"n": state["n"] + 1})
    graph.add_edge(START, "step")
    graph.add_conditional_edges(
        "step",
        lambda state: END if stop_at is not None and state["n"] >= stop_at else "step",
    )
    return graph.compile()


def test_bounded_graph_completes_with_and_without_observer():
    plain = invoke_bounded(counter(3), {"n": 0}, name="c", recursion_limit=10)
    assert plain == {"n": 3}
    started: list[str] = []
    final = invoke_bounded(
        counter(3), {"n": 0}, name="c", recursion_limit=10, on_node_start=started.append
    )
    assert final == {"n": 3} and started == ["step", "step", "step"]


@pytest.mark.parametrize("observer", [None, lambda node: None])
def test_unbounded_loop_becomes_a_typed_workflow_error(observer):
    with pytest.raises(WorkflowLimitError, match="counter exceeded its step limit"):
        invoke_bounded(
            counter(None),
            {"n": 0},
            name="counter",
            recursion_limit=4,
            on_node_start=observer,
        )
    assert issubclass(WorkflowLimitError, RepoAgentError)


def test_diagrams_cover_every_workflow_and_its_loops():
    diagrams = workflow_diagrams()
    assert set(diagrams) == WORKFLOWS
    assert "refine --> retrieve" in diagrams["investigator"]
    assert "revision --> develop" in diagrams["patch_review"]
    assert "analyze -.-> reinvestigate" in diagrams["sandbox_repair"]
    assert "deduplicate -.-> results" in diagrams["discovery_workflow"]
    assert set(workflow_diagrams("investigator")) == {"investigator"}
    with pytest.raises(ValueError, match="Unknown workflow"):
        workflow_diagrams("missing")


def test_workflow_diagram_cli():
    runner = CliRunner()
    text = runner.invoke(app, ["workflow-diagram", "patch_review"])
    assert text.exit_code == 0 and text.output.startswith("%% patch_review")
    data = runner.invoke(app, ["workflow-diagram", "--json"])
    assert set(json.loads(data.output)) == WORKFLOWS
    bad = runner.invoke(app, ["workflow-diagram", "missing"])
    assert bad.exit_code == 2
