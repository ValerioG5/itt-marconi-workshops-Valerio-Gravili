from app.clients.base_client import BaseHttpClient


class EventClient(BaseHttpClient):
    """Client HTTP verso event-service."""

    def get_event(self, event_id: str) -> dict:
        """Recupera un evento. Solleva ReferenceNotFoundError / DependencyUnavailableError."""
        return self._get("/api/v1/events", event_id)
