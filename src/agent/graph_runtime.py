"""Invoke compiled LangGraph graphs under an explicit, named step budget.

Every RepoAgent graph is bounded by construction, so reaching LangGraph's
recursion limit means a routing bug or an undersized budget. It surfaces as
a typed ``WorkflowLimitError`` (a readable job/API error) instead of a raw
framework exception that jobs can only record as "Internal error".

``on_node_start`` observes node starts through LangGraph's own ``tasks``
stream. With ``subgraphs=True`` that stream also carries the nodes of graphs
invoked inside a node (Investigator, Developer/Reviewer, sandbox loop), so
nested progress needs no callback framework.
"""

from collections.abc import Callable
from typing import Any

from langgraph.errors import GraphRecursionError

from repoagent.domain.errors import WorkflowLimitError

NodeObserver = Callable[[str], None]


def invoke_bounded(
    graph: Any,
    state: Any,
    *,
    name: str,
    recursion_limit: int,
    on_node_start: NodeObserver | None = None,
) -> dict[str, Any]:
    """Run ``graph`` to completion or raise ``WorkflowLimitError``."""
    config: Any = {"recursion_limit": recursion_limit, "run_name": name}
    try:
        if on_node_start is None:
            return graph.invoke(state, config=config)
        return _streamed(graph, state, config, on_node_start)
    except GraphRecursionError:
        raise WorkflowLimitError(
            f"{name} exceeded its step limit of {recursion_limit} "
            "without reaching a terminal node"
        ) from None


def _streamed(
    graph: Any, state: Any, config: Any, on_node_start: NodeObserver
) -> dict[str, Any]:
    final: dict[str, Any] = {}
    for namespace, mode, data in graph.stream(
        state, config=config, stream_mode=["tasks", "values"], subgraphs=True
    ):
        if mode == "tasks" and "input" in data:  # a task start, not its result
            on_node_start(data["name"])
        elif mode == "values" and not namespace:  # top-level state only
            final = data
    return final
