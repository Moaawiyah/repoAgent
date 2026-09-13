"""Conservative classification of import origins."""

import sys

from repoagent.analysis.models import ImportOrigin


class ImportClassifier:
    """Classifies imports as internal, standard library, or external.

    An import is internal only when its module or its top-level package is
    known to exist in the analyzed repository; otherwise it is external.
    Relative imports resolve against the importing module and stay unknown
    when the target cannot be confirmed.
    """

    def __init__(self, internal_modules: set[str]) -> None:
        self._internal = frozenset(internal_modules)
        self._stdlib = frozenset(sys.stdlib_module_names)
        self._internal_tops = frozenset(
            module.split(".")[0] for module in self._internal
        )

    def classify(self, module: str, importer: str) -> ImportOrigin:
        """Return the origin of ``module`` as imported from ``importer``."""
        if module.startswith("."):
            return self._relative(module, importer)
        if module in self._internal:
            return ImportOrigin.INTERNAL
        top = module.split(".")[0]
        if top in self._stdlib:
            return ImportOrigin.STDLIB
        if top in self._internal_tops:
            return ImportOrigin.INTERNAL
        return ImportOrigin.EXTERNAL

    def _relative(self, module: str, importer: str) -> ImportOrigin:
        level = len(module) - len(module.lstrip("."))
        tail = module[level:]
        package = importer.split(".")
        if len(package) < level - 1:
            return ImportOrigin.UNKNOWN
        base = package[: len(package) - (level - 1)]
        candidate = ".".join([*base, tail]) if tail else ".".join(base)
        if candidate in self._internal:
            return ImportOrigin.INTERNAL
        return ImportOrigin.UNKNOWN
