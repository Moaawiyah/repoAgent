"""Atomic JSON report writes kept outside the analyzed repository."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import UUID

from repoagent.domain.errors import StorageError


def write_report(directory: Path, identifier: str, repository: str, text: str) -> Path:
    """Persist ``text`` as ``<uuid>.json``; refuse locations inside the target."""
    name = str(UUID(identifier))
    folder = directory.expanduser().resolve()
    if folder.is_relative_to(Path(repository).resolve()):
        raise StorageError("Report storage must be outside the repository")
    temporary = None
    try:
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{name}.json"
        with NamedTemporaryFile(mode="w", dir=folder, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
        return target
    except OSError:
        raise StorageError("Could not persist report") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
