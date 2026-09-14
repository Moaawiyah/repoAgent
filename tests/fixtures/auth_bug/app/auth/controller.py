"""Sign-in handling for the web tier."""

from app.auth.service import AuthService


def login_route(service: AuthService, email: str, password: str) -> str:
    """Handle a sign-in attempt from an HTTP request."""
    return service.login(email, password)
