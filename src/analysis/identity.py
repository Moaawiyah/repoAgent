"""Stable per-symbol identities shared by chunking and graph building."""

from repoagent.analysis.models import CodeSymbol


def symbol_node_ids(symbols: list[CodeSymbol]) -> list[tuple[CodeSymbol, str]]:
    """Pair each symbol of one file with its unique graph node ID.

    Python allows several symbols to share a qualified name (property
    getter/setter/deleter, conditional redefinitions). The first keeps the
    bare qualified name; later ones become ``name#2``, ``name#3`` in source
    order. Chunker and graph builder both call this, so a chunk and its
    graph node always agree on identity without matching by name.
    """
    seen: dict[str, int] = {}
    paired: list[tuple[CodeSymbol, str]] = []
    for symbol in symbols:
        base = symbol.qualified_name
        count = seen[base] = seen.get(base, 0) + 1
        paired.append((symbol, base if count == 1 else f"{base}#{count}"))
    return paired
