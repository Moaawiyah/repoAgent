"""Base service definitions."""


class BaseService:
    """Common service behaviour."""

    def __init__(self, name: str) -> None:
        self.name = name

    def describe(self) -> str:
        """Return a short description."""
        return f"service:{self.name}"
