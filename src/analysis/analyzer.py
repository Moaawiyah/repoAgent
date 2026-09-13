"""Repository analysis orchestration: source, discovery, parsing, relations."""

import logging

from repoagent.analysis.discovery import FileDiscovery
from repoagent.analysis.imports import ImportClassifier
from repoagent.analysis.python_ast import PythonAnalyzer
from repoagent.analysis.relations import RelationshipBuilder
from repoagent.analysis.results import FileAnalysis, RepositoryAnalysis
from repoagent.analysis.source import LocalRepositorySource, RepositorySource
from repoagent.domain.repository import RepositorySpec


def is_test_path(relative: str) -> bool:
    """Detect likely test modules by path segment or file stem."""
    parts = relative.split("/")
    stem = parts[-1].removesuffix(".py")
    return (
        "tests" in parts[:-1]
        or "test" in parts[:-1]
        or stem.startswith("test_")
        or stem.endswith("_test")
    )


class RepositoryAnalyzer:
    """Transforms a repository source tree into a typed analysis result."""

    def __init__(self, source: RepositorySource | None = None) -> None:
        self._source = source or LocalRepositorySource()

    def analyze(self, spec: RepositorySpec) -> RepositoryAnalysis:
        """Produce a deterministic analysis for the repository specification."""
        root = self._source.materialize(spec)
        found = FileDiscovery(root).discover()
        parser = PythonAnalyzer()
        files = [
            parser.analyze(relative, root / relative) for relative in found.python_files
        ]
        files = self._classify(files)
        relationships = RelationshipBuilder({file.module_name for file in files}).build(
            files
        )
        analysis = RepositoryAnalysis(
            repository_name=root.name,
            repository_root=str(root),
            discovered_files=found.file_count,
            python_files=len(found.python_files),
            config_files=list(found.metadata_files),
            test_files=[
                relative for relative in found.python_files if is_test_path(relative)
            ],
            modules=list(found.python_files),
            files=files,
            relationships=relationships,
        )
        logging.getLogger(__name__).debug(
            "Repository analyzed", extra={"event": "repository_analyzed"}
        )
        return analysis

    @staticmethod
    def _classify(files: list[FileAnalysis]) -> list[FileAnalysis]:
        classifier = ImportClassifier({file.module_name for file in files})
        return [
            file.model_copy(
                update={
                    "imports": [
                        imp.model_copy(
                            update={
                                "origin": classifier.classify(
                                    imp.module, file.module_name
                                )
                            }
                        )
                        for imp in file.imports
                    ]
                }
            )
            for file in files
        ]
