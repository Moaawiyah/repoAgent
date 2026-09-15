"""Logging level selection."""


def log_level(debug: bool) -> str:
    """Verbose logging only in debug mode."""
    return "DEBUG" if debug else "INFO"
