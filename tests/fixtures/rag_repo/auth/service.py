"""Authentication services for account access."""

from auth.tokens import issue_token


class AuthService:
    """Verifies credentials and opens sessions for accounts."""

    def __init__(self, pepper: str) -> None:
        self._pepper = pepper

    def authenticate(self, username: str, password: str) -> bool:
        """Check an account's credentials before opening a session."""
        return self.verify_password(password, self._digest(username))

    def verify_password(self, plaintext: str, hashed: str) -> bool:
        """Compare a candidate secret against the stored digest."""
        return hashed == self._digest(plaintext)

    def _digest(self, plaintext: str) -> str:
        return f"sha256:{self._pepper}:{plaintext}"

    async def refresh_session(self, account_id: str) -> str:
        """Issue a fresh session token for an existing account."""
        return issue_token(account_id)
