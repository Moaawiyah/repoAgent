"""Password and session checking for the demo application."""

from app.users.repository import UserRepository

SECRETS = {"ada": "lovelace"}


class AuthService:
    """Verifies credentials for login."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    def login(self, email: str, password: str) -> str:
        """Open a session when the credentials match an account."""
        user = self._users.find_by_email(email)
        username = user["username"]
        if SECRETS.get(username) != password:
            raise ValueError("bad credentials")
        return f"session:{username}"
