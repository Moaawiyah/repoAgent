"""Errors safe to present at application boundaries."""


class RepoAgentError(Exception):
    """An operational application failure."""


class TaskNotFound(RepoAgentError):
    """No task has the requested identifier."""


class InvalidTransition(RepoAgentError):
    """The requested lifecycle transition is disallowed."""


class UnsupportedSchema(RepoAgentError):
    """The database requires a different application schema."""
