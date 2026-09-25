import uuid
from datetime import datetime, timezone

from app.repository.base import (
    EventNotFoundError,
    InvalidOrganizerError,
    InvalidStatusTransitionError,
    ValidationError,
)

# REQ-EVT-B04 — transizioni ammesse, definite come dato e non come catena di if
_ALLOWED_TRANSITIONS = {
    "draft":     {"published", "cancelled"},
    "published": {"cancelled"},
    "cancelled": set(),          # stato terminale
}


class EventService:
    """Business logic di event-service. Non conosce Flask né requests."""

    def __init__(self, repository, user_client):
        self.repository = repository
        self.user_client = user_client

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _assert_valid_organizer(self, organizer_id: str) -> None:
        """REQ-EVT-B01 + REQ-EVT-B02.

        Il client solleva OrganizerNotFoundError (404 remoto) o
        DependencyUnavailableError (timeout/connessione/5xx). Qui si aggiunge
        solo il controllo sul ruolo, così la distinzione tra
        REFERENCE_NOT_FOUND e INVALID_ORGANIZER resta in un unico punto.
        """
        user = self.user_client.get_user(organizer_id)
        if user.get("role") != "organizer":
            raise InvalidOrganizerError(organizer_id)

    @staticmethod
    def _assert_dates_coherent(start_date: str, end_date: str) -> None:
        """REQ-EVT-B03. Il formato YYYY-MM-DD rende il confronto
        lessicografico equivalente a quello cronologico."""
        if end_date < start_date:
            raise ValidationError("end_date must be greater than or equal to start_date")

    @staticmethod
    def _assert_valid_transition(current: str, requested: str) -> None:
        """REQ-EVT-B04."""
        if requested == current:
            return                       # no-op ammesso (criterio 6)
        if requested not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidStatusTransitionError(f"{current} -> {requested}")

    # ------------------------------------------------------------------
    # T-08 — create / read / list / delete
    # ------------------------------------------------------------------

    def create_event(self, data: dict) -> dict:
        """REQ-EVT-E01. Valida date e organizzatore, poi persiste."""
        self._assert_dates_coherent(data["start_date"], data["end_date"])
        self._assert_valid_organizer(data["organizer_id"])

        now = self._now()
        event = {
            "id": str(uuid.uuid4()),
            "title": data["title"],
            "description": data.get("description"),
            "organizer_id": data["organizer_id"],
            "venue": data["venue"],
            "city": data["city"],
            "start_date": data["start_date"],
            "end_date": data["end_date"],
            "capacity": data["capacity"],
            "price": data["price"],
            "status": data.get("status", "draft"),
            "created_at": now,
            "updated_at": now,
        }
        return self.repository.save(event)

    def get_event(self, event_id: str) -> dict:
        """REQ-EVT-E03."""
        event = self.repository.find_by_id(event_id)
        if event is None:
            raise EventNotFoundError(f"Event '{event_id}' not found")
        return event

    def list_events(self, status, city, page: int, page_size: int):
        """REQ-EVT-E02 + REQ-EVT-B06. Restituisce (page_items, total)."""
        all_items = self.repository.list_all(status, city)
        total = len(all_items)
        start = (page - 1) * page_size
        return all_items[start:start + page_size], total

    def delete_event(self, event_id: str) -> None:
        """REQ-EVT-E06."""
        self.repository.delete(event_id)

    # ------------------------------------------------------------------
    # T-09 — replace / update con transizioni di stato
    # ------------------------------------------------------------------

    def replace_event(self, event_id: str, data: dict) -> dict:
        """REQ-EVT-E04. Sostituzione completa; preserva id e created_at."""
        existing = self.repository.find_by_id(event_id)
        if existing is None:
            raise EventNotFoundError(f"Event '{event_id}' not found")

        self._assert_dates_coherent(data["start_date"], data["end_date"])
        self._assert_valid_organizer(data["organizer_id"])

        # REQ-EVT-E04 criterio 8: se status assente preserva quello stored
        requested_status = data.get("status", existing["status"])
        self._assert_valid_transition(existing["status"], requested_status)

        event = {
            "id": existing["id"],
            "title": data["title"],
            "description": data.get("description"),
            "organizer_id": data["organizer_id"],
            "venue": data["venue"],
            "city": data["city"],
            "start_date": data["start_date"],
            "end_date": data["end_date"],
            "capacity": data["capacity"],
            "price": data["price"],
            "status": requested_status,
            "created_at": existing["created_at"],
            "updated_at": self._now(),
        }
        return self.repository.update(event)

    def update_event(self, event_id: str, data: dict) -> dict:
        """REQ-EVT-E05. Aggiornamento parziale."""
        existing = self.repository.find_by_id(event_id)
        if existing is None:
            raise EventNotFoundError(f"Event '{event_id}' not found")

        # REQ-EVT-B03 criteri 3-5: valida sul MERGE tra stored e nuovo
        merged_start = data.get("start_date", existing["start_date"])
        merged_end = data.get("end_date", existing["end_date"])
        self._assert_dates_coherent(merged_start, merged_end)

        # REQ-EVT-B01 criterio 5: nessuna chiamata se organizer_id non c'e'
        if "organizer_id" in data:
            self._assert_valid_organizer(data["organizer_id"])

        if "status" in data:
            self._assert_valid_transition(existing["status"], data["status"])

        updated = dict(existing)
        for field in (
            "title", "description", "organizer_id", "venue", "city",
            "start_date", "end_date", "capacity", "price", "status",
        ):
            if field in data:
                updated[field] = data[field]

        updated["updated_at"] = self._now()
        return self.repository.update(updated)
