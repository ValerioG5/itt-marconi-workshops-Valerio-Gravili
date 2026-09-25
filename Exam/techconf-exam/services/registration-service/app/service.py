import threading
import uuid
from datetime import datetime, timezone

from app.repository.base import (
    AlreadyRegisteredError,
    EventFullError,
    EventNotFoundForStatsError,
    EventNotOpenError,
    InvalidStatusTransitionError,
    ReferenceNotFoundError,
    RegistrationNotFoundError,
)

# REQ-REG-B07 — l'unica transizione ammessa è confirmed -> cancelled
_ALLOWED_TRANSITIONS = {
    "confirmed": {"cancelled"},
    "cancelled": set(),        # stato terminale
}


class RegistrationService:
    """Business logic delle registrazioni.

    Non conosce Flask né requests: riceve repository e client come dipendenze.
    """

    def __init__(self, repository, user_client, event_client):
        self.repository = repository
        self.user_client = user_client
        self.event_client = event_client
        # Serializza la sezione critica duplicato+capienza+scrittura.
        # Volutamente NON tenuto durante le chiamate di rete: vedi design §3.2.
        self._seat_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def _assert_valid_transition(current: str, requested: str) -> None:
        """REQ-REG-B07."""
        if requested == current:
            return                       # no-op ammesso (criterio 4)
        if requested not in _ALLOWED_TRANSITIONS.get(current, set()):
            raise InvalidStatusTransitionError(f"{current} -> {requested}")

    # ------------------------------------------------------------------
    # T-08 — creazione con capienza
    # ------------------------------------------------------------------

    def create_registration(self, data: dict) -> dict:
        """REQ-REG-E01. Ordine dei controlli come da design §3.2.

        Tutte le chiamate di rete precedono la sezione critica, così fra il
        conteggio dei posti e la scrittura non c'è alcuna attesa di I/O.
        """
        user_id = data["user_id"]
        event_id = data["event_id"]

        # Passi 2-3: I/O di rete. Propagano ReferenceNotFoundError (404 remoto)
        # e DependencyUnavailableError (timeout/connessione/5xx).
        self.user_client.get_user(user_id)             # REQ-REG-B01
        event = self.event_client.get_event(event_id)  # REQ-REG-B02

        # Passo 4: REQ-REG-B03
        if event.get("status") != "published":
            raise EventNotOpenError(event_id)

        # Passi 5-7: sezione critica, nessuna I/O di rete all'interno.
        with self._seat_lock:
            # REQ-REG-B04 — solo le 'confirmed' bloccano
            if self.repository.find_confirmed(user_id, event_id) is not None:
                raise AlreadyRegisteredError(
                    f"{user_id} already registered to {event_id}"
                )

            # REQ-REG-B05 — solo le 'confirmed' occupano posto
            if self.repository.count_confirmed(event_id) >= event["capacity"]:
                raise EventFullError(event_id)

            now = self._now()
            registration = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "event_id": event_id,
                "amount": event["price"],     # REQ-REG-B06: mai dal client
                "status": "confirmed",        # REQ-REG-E01 criterio 2
                "created_at": now,
                "updated_at": now,
            }
            return self.repository.save(registration)

    def get_registration(self, registration_id: str) -> dict:
        """REQ-REG-E03."""
        registration = self.repository.find_by_id(registration_id)
        if registration is None:
            raise RegistrationNotFoundError(
                f"Registration '{registration_id}' not found"
            )
        return registration

    def list_registrations(self, user_id, event_id, status, page: int, page_size: int):
        """REQ-REG-E02. Restituisce (page_items, total)."""
        all_items = self.repository.list_all(user_id, event_id, status)
        total = len(all_items)
        start = (page - 1) * page_size
        return all_items[start:start + page_size], total

    def delete_registration(self, registration_id: str) -> None:
        """REQ-REG-E05. Il record scompare, quindi non viene più contato."""
        self.repository.delete(registration_id)

    # ------------------------------------------------------------------
    # T-09 — transizioni di stato e statistiche
    # ------------------------------------------------------------------

    def update_status(self, registration_id: str, new_status: str) -> dict:
        """REQ-REG-B07 + REQ-REG-E04. Nessuna chiamata alle dipendenze."""
        existing = self.repository.find_by_id(registration_id)
        if existing is None:
            raise RegistrationNotFoundError(
                f"Registration '{registration_id}' not found"
            )

        self._assert_valid_transition(existing["status"], new_status)

        updated = dict(existing)
        updated["status"] = new_status
        updated["updated_at"] = self._now()
        return self.repository.update(updated)

    def get_stats(self, event_id: str) -> dict:
        """REQ-REG-B08.

        L'evento inesistente deve diventare 404, non 422: il ReferenceNotFoundError
        del client viene quindi ritradotto in EventNotFoundForStatsError.
        """
        try:
            event = self.event_client.get_event(event_id)
        except ReferenceNotFoundError as exc:
            raise EventNotFoundForStatsError(event_id) from exc

        confirmed = self.repository.count_confirmed(event_id)
        capacity = event["capacity"]
        return {
            "event_id": event_id,
            "capacity": capacity,
            "confirmed": confirmed,
            "available": max(0, capacity - confirmed),   # criterio 4: mai negativo
        }
