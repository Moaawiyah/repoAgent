"""Sign-in flow controller for the web tier."""

from auth.service import AuthService


class AuthController:
    """Coordinates sign-in attempts against the account service."""

    def __init__(self, service: AuthService) -> None:
        self._service = service

    def login(self, username: str, password: str) -> bool:
        """Handle a sign-in attempt end to end."""
        return self._service.authenticate(username, password)
