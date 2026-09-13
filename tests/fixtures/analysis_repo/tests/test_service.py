"""Fixture tests detected by repository analysis."""

from app.service import UserService


def test_authenticate() -> None:
    service = UserService("fixture")
    assert service.authenticate("u", "p")
