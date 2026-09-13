"""Repository source abstraction: local directories now, remotes later."""

import os
from pathlib import Path
from typing import Protocol

from repoagent.domain.errors import RepositoryInvalid
from repoagent.domain.repository import RepositorySpec


class RepositorySource(Protocol):
    """Materializes a repository specification into a local source tree."""

    def materialize(self, spec: RepositorySpec) -> Path: ...


class LocalRepositorySource:
    """Validates that the specification is a readable local directory."""

    def materialize(self, spec: RepositorySpec) -> Path:
        root = Path(spec.source)
        if not root.is_dir():
            raise RepositoryInvalid("Repository source is not an accessible directory")
        if not self._readable(root):
            raise RepositoryInvalid("Repository directory is not readable")
        return root

    @staticmethod
    def _readable(root: Path) -> bool:
        if not (os.access(root, os.R_OK) and os.access(root, os.X_OK)):
            return False
        try:
            with os.scandir(root):
                return True
        except OSError:
            return False
