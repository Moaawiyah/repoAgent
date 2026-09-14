"""In-memory user repository."""

from app.models import UserNotFoundError


class UserRepository:
    """Stores accounts and answers email lookups."""

    def __init__(self, users: list[dict[str, str]]) -> None:
        self._users = users

    def find_by_email(self, email: str) -> dict[str, str]:
        """Locate an account by its email address."""
        for user in self._users:
            if user["email"] == email:
                return user
        raise UserNotFoundError(email)

    def count(self) -> int:
        """Return the number of stored accounts."""
        return len(self._users)
