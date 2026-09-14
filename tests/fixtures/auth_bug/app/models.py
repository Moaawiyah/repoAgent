"""Account and session models for the demo application."""


def normalize_email(email: str) -> str:
    """Lowercase and strip an email address for storage."""
    return email.strip().lower()


class UserNotFoundError(Exception):
    """Raised when no account matches the provided email."""
