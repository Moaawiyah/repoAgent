"""CircularDependencyDetector and CouplingDetector, over the real graph."""

from repoagent.audit.detectors.coupling import CouplingDetector
from repoagent.audit.detectors.graph_cycles import (
    CircularDependencyDetector,
    find_cycles,
)
from tests.support.audit import build_context


def test_flags_circular_module_import():
    found = CircularDependencyDetector().detect(build_context())
    assert len(found) == 1
    candidate = found[0]
    assert "cycle_a.py" in candidate.description
    assert "cycle_b.py" in candidate.description


def test_find_cycles_dedupes_rotations():
    adjacency = {"a": ["b"], "b": ["c"], "c": ["a"]}
    cycles = find_cycles(adjacency)
    assert len(cycles) == 1


def test_find_cycles_ignores_acyclic_graph():
    adjacency = {"a": ["b"], "b": ["c"], "c": []}
    assert find_cycles(adjacency) == []


def test_flags_highly_coupled_hub_function():
    found = CouplingDetector().detect(build_context())
    assert any(c.symbol == "hub.process" for c in found)


def test_does_not_flag_low_fan_symbols():
    found = CouplingDetector().detect(build_context())
    assert not any(c.symbol and c.symbol.startswith("clean.") for c in found)
