"""Retrieval model validation, chunk identity, and index persistence."""

import pytest
from pydantic import ValidationError

from repoagent.adapters.index_store import JsonIndexStore
from repoagent.domain.errors import IndexNotFound, StorageError
from repoagent.retrieval.models import (
    CodeChunk,
    IndexSnapshot,
    SearchRequest,
    SymbolType,
    make_chunk_id,
    repository_identifier,
)


def make_chunk(source="x = 1"):
    return CodeChunk(
        chunk_id=make_chunk_id("r", "a.py", "a.value", source),
        repository_id="r",
        file_path="a.py",
        language="python",
        symbol_name="value",
        qualified_name="a.value",
        symbol_type=SymbolType.FUNCTION,
        start_line=1,
        end_line=1,
        source=source,
        docstring="Doc.",
    )


def test_chunk_id_is_deterministic_and_source_sensitive():
    first = make_chunk_id("r", "a.py", "a.value", "x = 1")
    assert first == make_chunk_id("r", "a.py", "a.value", "x = 1")
    assert first != make_chunk_id("r", "a.py", "a.value", "x = 2")
    assert first != make_chunk_id("other", "a.py", "a.value", "x = 1")


def test_search_text_combines_provenance_and_source():
    text = make_chunk().search_text
    assert "a.py" in text and "a.value" in text and "Doc." in text
    assert text.endswith("x = 1")


def test_repository_identifier_is_stable_and_named():
    identifier = repository_identifier("/tmp/demo")
    assert identifier == repository_identifier("/tmp/demo")
    assert identifier.startswith("demo-")


def test_search_request_validates_query_and_top_k():
    request = SearchRequest(repository="./repo", query="  find auth  ")
    assert request.query == "find auth"
    assert request.strategy.value == "hybrid"
    assert request.top_k == 5
    with pytest.raises(ValidationError):
        SearchRequest(repository="./repo", query="   ")
    with pytest.raises(ValidationError):
        SearchRequest(repository="./repo", query="auth", top_k=0)


def test_index_store_roundtrip(tmp_path):
    store = JsonIndexStore(tmp_path / "indexes")
    snapshot = IndexSnapshot(
        repo_id="demo-1",
        repository_root="/tmp/demo",
        embedding_provider="hashing",
        embedding_dimension=256,
        chunks=[make_chunk()],
        vectors={make_chunk().chunk_id: [0.5, 0.5]},
    )
    store.save(snapshot)
    assert store.exists("demo-1")
    assert store.load("demo-1") == snapshot


def test_missing_index_raises_typed_error(tmp_path):
    store = JsonIndexStore(tmp_path / "indexes")
    assert not store.exists("nope")
    with pytest.raises(IndexNotFound):
        store.load("nope")


def test_corrupt_index_raises_storage_error(tmp_path):
    base = tmp_path / "indexes"
    store = JsonIndexStore(base)
    base.mkdir()
    (base / "broken.json").write_text("not json", encoding="utf-8")
    with pytest.raises(StorageError):
        store.load("broken")


def test_failed_save_raises_storage_error(tmp_path):
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory", encoding="utf-8")
    store = JsonIndexStore(blocked / "indexes")
    snapshot = IndexSnapshot(
        repo_id="demo-1",
        repository_root="/tmp/demo",
        embedding_provider="hashing",
        embedding_dimension=256,
        chunks=[],
    )
    with pytest.raises(StorageError):
        store.save(snapshot)
