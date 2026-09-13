"""Fixture tests for authentication."""

from auth.service import AuthService


def test_verify_password_rejects_wrong_secret() -> None:
    service = AuthService("pepper")
    assert not service.verify_password("right", "sha256:pepper:wrong")
