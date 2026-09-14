"""Typed symbol, import, and relationship models for repository analysis."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class AnalysisModel(BaseModel):
    """Immutable, strict base for analysis values."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class SymbolType(StrEnum):
    """Kinds of statically extractable code symbols."""

    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"


class ImportOrigin(StrEnum):
    """Conservative classification of where an import resolves."""

    INTERNAL = "internal"
    STDLIB = "stdlib"
    EXTERNAL = "external"
    UNKNOWN = "unknown"


class RelationKind(StrEnum):
    """Relationships derivable from static analysis alone."""

    IMPORTS = "imports"
    INHERITS = "inherits"
    CONTAINS = "contains"
    DEFINES = "defines"


class Parameter(AnalysisModel):
    """A function or method parameter with optional annotation/default."""

    name: str
    annotation: str | None = None
    default: str | None = None
    kind: str = "positional_or_keyword"


class ImportedName(AnalysisModel):
    """A symbol imported by a ``from`` statement, with optional alias."""

    name: str
    alias: str | None = None


class ImportInfo(AnalysisModel):
    """One import statement: ``import m`` has no names, ``from m`` has names."""

    module: str
    line: int
    names: list[ImportedName] = Field(default_factory=list)
    origin: ImportOrigin = ImportOrigin.UNKNOWN


class CodeSymbol(AnalysisModel):
    """A statically extracted code symbol with location and metadata."""

    name: str
    qualified_name: str
    file_path: str
    symbol_type: SymbolType
    start_line: int
    end_line: int
    parent: str | None = None
    is_async: bool = False
    parameters: list[Parameter] = Field(default_factory=list)
    return_annotation: str | None = None
    docstring: str | None = None
    decorators: list[str] = Field(default_factory=list)
    bases: list[str] = Field(default_factory=list)


class Relationship(AnalysisModel):
    """A directed static relation; ``resolved`` marks internal targets."""

    kind: RelationKind
    source: str
    target: str
    resolved: bool = False


class CallSite(AnalysisModel):
    """A raw call expression inside a symbol, unresolved at parse time."""

    caller: str
    expression: str
    line: int
