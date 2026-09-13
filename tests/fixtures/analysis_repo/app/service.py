"""User services demonstrating inheritance and async definitions."""

from app.base import BaseService


class UserService(BaseService):
    """Manage application users."""

    def authenticate(self, username: str, password: str) -> bool:
        """Check credentials."""
        return bool(username and password)

    async def fetch_profile(self, user_id: int) -> dict[str, str]:
        """Load a user profile asynchronously."""
        return {"id": str(user_id)}


def create_service(name: str = "default") -> UserService:
    """Factory helper."""
    return UserService(name)
