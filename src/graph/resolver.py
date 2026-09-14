"""Conservative static resolution of call expressions to graph nodes.

Python calls cannot be resolved perfectly without execution. This
resolver returns explicit certainty levels instead of guessing:

- resolved: exactly one internal node is determined;
- partial: the callee name is internal but the instance is unknown;
- unresolved: no safe internal target (external, builtin, dynamic).

The ``None`` result means "do not create an edge".
"""

from repoagent.graph.models import GraphNode
from repoagent.graph.store import InMemoryGraphStore

_SELF_PREFIXES = ("self.", "cls.")


class CallResolver:
    """Maps call expressions written inside a caller to target node IDs."""

    def __init__(self, store: InMemoryGraphStore) -> None:
        self._store = store

    def resolve(self, caller: GraphNode, expression: str) -> tuple[str, bool] | None:
        """Return ``(target_id, resolved)`` or ``None`` when unresolved."""
        if self._store.has_node(expression):
            return expression, True
        direct_self = (
            expression.startswith(_SELF_PREFIXES) and expression.count(".") == 1
        )
        if direct_self:
            return self._resolve_bound(caller, expression)
        if "." not in expression:
            return self._resolve_bare(caller, expression)
        return self._resolve_attribute(expression)

    def _resolve_bound(
        self, caller: GraphNode, expression: str
    ) -> tuple[str, bool] | None:
        """Resolve ``self.name()`` against the caller's own class."""
        if not caller.parent:
            return None
        method = expression.split(".")[-1]
        candidate = f"{caller.parent}.{method}"
        if self._store.has_node(candidate):
            return candidate, True
        return None

    def _resolve_bare(
        self, caller: GraphNode, expression: str
    ) -> tuple[str, bool] | None:
        """Resolve a bare name: same module first, then unique repo-wide."""
        local = f"{caller.module}.{expression}"
        if self._store.has_node(local):
            return local, True
        candidates = self._store.nodes_by_simple_name(expression)
        if len(candidates) == 1:
            return candidates[0], True
        return None

    def _resolve_attribute(self, expression: str) -> tuple[str, bool] | None:
        """Resolve ``obj.attr(...)`` by qualified suffix or unique name.

        A unique qualified-suffix match is fully resolved. Otherwise a
        unique simple-name match stays partial: the callee name exists
        internally, but the receiving instance is statically unknown.
        """
        matches = [
            node_id
            for node_id in sorted(self._store.node_ids())
            if node_id.endswith("." + expression)
        ]
        if len(matches) == 1:
            return matches[0], True
        name = expression.split(".")[-1]
        candidates = self._store.nodes_by_simple_name(name)
        if len(candidates) == 1:
            return candidates[0], False
        return None
