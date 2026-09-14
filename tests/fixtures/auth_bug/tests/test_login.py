"""Fixture tests for login behavior."""

from app.auth.service import AuthService
from app.users.repository import UserRepository

USERS = [{"email": "ada@example.com", "username": "ada"}]


def test_login_succeeds_for_stored_account() -> None:
    service = AuthService(UserRepository(USERS))
    assert service.login("ada@example.com", "lovelace").startswith("session:")
