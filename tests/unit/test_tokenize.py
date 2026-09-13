"""Identifier-aware tokenization behavior."""

from repoagent.retrieval.tokenize import split_identifier, tokenize


def test_snake_case_keeps_identifier_and_adds_subtokens():
    assert split_identifier("authenticate_user") == [
        "authenticate_user",
        "authenticate",
        "user",
    ]


def test_camel_case_keeps_identifier_and_adds_subtokens():
    assert split_identifier("AuthService") == ["authservice", "auth", "service"]


def test_abbreviations_and_mixed_separators():
    assert split_identifier("GetHTTPResponse_code") == [
        "gethttpresponse_code",
        "get",
        "http",
        "response",
        "code",
    ]


def test_plain_identifier_is_lowered_only():
    assert split_identifier("token") == ["token"]


def test_tokenize_finds_identifiers_in_free_text():
    tokens = tokenize("Where is verify_password used in AuthService?")
    assert "verify_password" in tokens
    assert "verify" in tokens and "password" in tokens
    assert "auth" in tokens and "service" in tokens
    assert "?" not in tokens


def test_empty_text_yields_no_tokens():
    assert tokenize("") == []
    assert tokenize("!!! ...") == []
