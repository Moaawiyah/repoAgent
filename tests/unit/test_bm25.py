"""BM25 ranking behavior over code chunks."""

from repoagent.retrieval.bm25 import BM25Index, BM25Retriever
from repoagent.retrieval.models import CodeChunk, SymbolType, make_chunk_id


def make_chunk(qualified, source, stype=SymbolType.FUNCTION, doc=None):
    return CodeChunk(
        chunk_id=make_chunk_id("r", f"{qualified}.py", qualified, source),
        repository_id="r",
        file_path=f"{qualified}.py",
        language="python",
        symbol_name=qualified.split(".")[-1],
        qualified_name=qualified,
        symbol_type=stype,
        start_line=1,
        end_line=source.count("\n") + 1,
        source=source,
        docstring=doc,
    )


CHUNKS = [
    make_chunk(
        "auth.authenticate_user",
        "def authenticate_user(username, password):\n"
        "    '''Verify credentials for login.'''\n",
        doc="Verify credentials for login.",
    ),
    make_chunk(
        "auth.AuthService",
        "class AuthService:\n    '''Session service for accounts.'''\n",
        stype=SymbolType.CLASS,
        doc="Session service for accounts.",
    ),
    make_chunk(
        "billing.calculate_invoice_total",
        "def calculate_invoice_total(lines):\n    return sum(amount for lines)\n",
    ),
]


def search(query, top_k=3):
    return BM25Retriever(CHUNKS).search(query, top_k)


def test_exact_identifiers_rank_first():
    results = search("calculate_invoice_total")
    assert results[0].chunk.qualified_name == "billing.calculate_invoice_total"
    assert results[0].source.value == "bm25"
    assert results[0].rank == 1


def test_snake_case_query_matches_normalized_identifier():
    results = search("authenticate user")
    assert results[0].chunk.qualified_name == "auth.authenticate_user"


def test_camel_case_query_matches_class_identifier():
    results = search("auth service")
    assert results[0].chunk.qualified_name == "auth.AuthService"


def test_top_k_is_respected():
    assert len(search("auth", top_k=1)) == 1
    assert len(search("auth service invoice authenticate", top_k=2)) == 2


def test_unknown_terms_return_no_results():
    assert search("qqqzzz nonexistent") == []


def test_empty_index_and_queries_are_safe():
    assert BM25Index([]).search("anything", 5) == []
    assert BM25Retriever(CHUNKS).search("", 5) == []
