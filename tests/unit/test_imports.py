"""Import origin classification."""

from repoagent.analysis.imports import ImportClassifier
from repoagent.analysis.models import ImportOrigin

CLASSIFIER = ImportClassifier({"app", "app.service", "app.utils"})


def test_internal_modules_packages_and_unloaded_submodules():
    assert CLASSIFIER.classify("app.service", "x") is ImportOrigin.INTERNAL
    assert CLASSIFIER.classify("app", "x") is ImportOrigin.INTERNAL
    assert CLASSIFIER.classify("app.utils.extra", "x") is ImportOrigin.INTERNAL


def test_stdlib_and_external_classification():
    assert CLASSIFIER.classify("os.path", "x") is ImportOrigin.STDLIB
    assert CLASSIFIER.classify("collections", "x") is ImportOrigin.STDLIB
    assert CLASSIFIER.classify("requests", "x") is ImportOrigin.EXTERNAL
    assert CLASSIFIER.classify("unknownpkg.sub", "x") is ImportOrigin.EXTERNAL


def test_internal_takes_precedence_over_stdlib():
    shadowing = ImportClassifier({"email", "email.mime"})
    assert shadowing.classify("email.mime", "x") is ImportOrigin.INTERNAL
    assert ImportClassifier(set()).classify("email", "x") is ImportOrigin.STDLIB


def test_relative_imports_resolve_against_the_importer():
    assert CLASSIFIER.classify(".service", "app") is ImportOrigin.INTERNAL
    assert CLASSIFIER.classify("..service", "app.sub") is ImportOrigin.INTERNAL
    assert CLASSIFIER.classify(".", "app.service") is ImportOrigin.INTERNAL
    assert CLASSIFIER.classify(".service", "app.sub") is ImportOrigin.UNKNOWN
    assert CLASSIFIER.classify(".missing", "app") is ImportOrigin.UNKNOWN
    assert CLASSIFIER.classify("..beyond", "app") is ImportOrigin.UNKNOWN
