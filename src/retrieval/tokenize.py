"""Identifier-aware tokenization for lexical and hashed retrieval."""

import re

_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_SPLIT = re.compile(r"_+|(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def split_identifier(identifier: str) -> list[str]:
    """Split snake_case and CamelCase while keeping the whole identifier.

    ``authenticate_user`` yields ``authenticate_user``, ``authenticate``,
    and ``user``; ``AuthService`` yields ``authservice``, ``auth``, and
    ``service``. Exact identifiers are preserved alongside subtokens.
    """
    parts = [part for part in _SPLIT.split(identifier) if part]
    lowered = identifier.lower()
    if len(parts) <= 1:
        return [lowered]
    return [lowered, *(part.lower() for part in parts)]


def tokenize(text: str) -> list[str]:
    """Tokenize free text and code into searchable terms."""
    tokens: list[str] = []
    for identifier in _IDENTIFIER.findall(text):
        tokens.extend(split_identifier(identifier))
    return tokens
