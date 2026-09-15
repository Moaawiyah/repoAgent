"""Typed conversion of environment variable strings."""


def parse_bool(value: str) -> bool:
    """Interpret common textual boolean values."""
    return bool(value.strip())


def parse_int(value: str, default: int) -> int:
    """Parse an integer, falling back to a default for blanks."""
    text = value.strip()
    return int(text) if text else default
