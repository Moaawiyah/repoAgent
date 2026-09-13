"""File-level and repository-level analysis results."""

from pydantic import Field, computed_field

from repoagent.analysis.models import (
    AnalysisModel,
    CodeSymbol,
    ImportInfo,
    Relationship,
    SymbolType,
)


class FileError(AnalysisModel):
    """A per-file analysis failure that does not abort the repository run."""

    path: str
    error_type: str
    message: str


class FileAnalysis(AnalysisModel):
    """Parsed symbols and imports for one Python file, or its error."""

    path: str
    module_name: str
    line_count: int = 0
    symbols: list[CodeSymbol] = Field(default_factory=list)
    imports: list[ImportInfo] = Field(default_factory=list)
    error: FileError | None = None


class RepositoryAnalysis(AnalysisModel):
    """Structured, deterministic summary of an analyzed repository."""

    repository_name: str
    repository_root: str
    discovered_files: int
    python_files: int
    config_files: list[str] = Field(default_factory=list)
    test_files: list[str] = Field(default_factory=list)
    modules: list[str] = Field(default_factory=list)
    files: list[FileAnalysis] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def symbols(self) -> list[CodeSymbol]:
        """All extracted symbols across analyzed files."""
        return [symbol for file in self.files for symbol in file.symbols]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def imports(self) -> list[ImportInfo]:
        """All import statements across analyzed files."""
        return [imp for file in self.files for imp in file.imports]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def errors(self) -> list[FileError]:
        """Per-file failures recorded during analysis."""
        return [file.error for file in self.files if file.error is not None]

    def _count(self, symbol_type: SymbolType) -> int:
        return sum(1 for symbol in self.symbols if symbol.symbol_type is symbol_type)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def module_count(self) -> int:
        return self._count(SymbolType.MODULE)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def class_count(self) -> int:
        return self._count(SymbolType.CLASS)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def function_count(self) -> int:
        return self._count(SymbolType.FUNCTION)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def method_count(self) -> int:
        return self._count(SymbolType.METHOD)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def test_count(self) -> int:
        return len(self.test_files)
