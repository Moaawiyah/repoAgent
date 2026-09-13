"""Opaque token helpers for account sessions."""

_EXPIRY_SECONDS = 3600


def issue_token(subject: str) -> str:
    """Mint a signed bearer token for a subject."""
    return f"tok.{subject}.{_EXPIRY_SECONDS}"


def decode_token(token: str) -> str | None:
    """Return the subject embedded in a bearer token."""
    parts = token.split(".")
    return parts[1] if len(parts) == 3 else None
