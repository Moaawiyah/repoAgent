"""Deterministic audit detectors: AST/graph rules plus the optional Ruff adapter."""

from repoagent.audit.detectors.base import Detector
from repoagent.audit.detectors.coupling import CouplingDetector
from repoagent.audit.detectors.dead_code import DeadCodeDetector
from repoagent.audit.detectors.defaults import MutableDefaultDetector
from repoagent.audit.detectors.exceptions import BroadExceptionDetector
from repoagent.audit.detectors.graph_cycles import CircularDependencyDetector
from repoagent.audit.detectors.none_handling import NoneDefaultAccessDetector
from repoagent.audit.detectors.resources import ResourceHandlingDetector
from repoagent.audit.detectors.ruff_adapter import RuffDetector
from repoagent.audit.detectors.subprocess_risk import SubprocessRiskDetector
from repoagent.audit.detectors.todo_markers import TodoMarkerDetector
from repoagent.ports.sandbox import SandboxRunner

__all__ = [
    "BroadExceptionDetector",
    "CircularDependencyDetector",
    "CouplingDetector",
    "DeadCodeDetector",
    "Detector",
    "MutableDefaultDetector",
    "NoneDefaultAccessDetector",
    "ResourceHandlingDetector",
    "RuffDetector",
    "SubprocessRiskDetector",
    "TodoMarkerDetector",
    "ast_detectors",
    "default_detectors",
    "graph_detectors",
]


def ast_detectors() -> list[Detector]:
    """LLM-free AST rules over parsed source."""
    return [
        BroadExceptionDetector(),
        MutableDefaultDetector(),
        NoneDefaultAccessDetector(),
        ResourceHandlingDetector(),
        SubprocessRiskDetector(),
        DeadCodeDetector(),
        TodoMarkerDetector(),
    ]


def graph_detectors() -> list[Detector]:
    """Rules over the native M4 repository graph."""
    return [CircularDependencyDetector(), CouplingDetector()]


def default_detectors(sandbox_runner: SandboxRunner | None = None) -> list[Detector]:
    """The standard detector set; Ruff only participates when sandboxed."""
    return [*ast_detectors(), *graph_detectors(), RuffDetector(sandbox_runner)]
