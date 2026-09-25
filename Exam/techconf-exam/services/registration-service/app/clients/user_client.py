from app.clients.base_client import BaseHttpClient


class UserClient(BaseHttpClient):
    """Client HTTP verso user-service."""

    def get_user(self, user_id: str) -> dict:
        """Recupera un utente. Solleva ReferenceNotFoundError / DependencyUnavailableError."""
        return self._get("/api/v1/users", user_id)
