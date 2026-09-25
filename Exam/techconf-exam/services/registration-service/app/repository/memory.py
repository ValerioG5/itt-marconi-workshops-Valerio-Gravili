from app.repository.base import (
    AbstractRegistrationRepository,
    RegistrationNotFoundError,
)


class MemoryRegistrationRepository(AbstractRegistrationRepository):
    """Backend in-process basato su dizionario."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def save(self, registration: dict) -> dict:
        """Inserisce una nuova registrazione nello store in memoria."""
        self._store[registration["id"]] = dict(registration)
        return dict(registration)

    def find_by_id(self, registration_id: str) -> dict | None:
        """Restituisce una copia della registrazione oppure None se non esiste."""
        reg = self._store.get(registration_id)
        return dict(reg) if reg is not None else None

    def find_confirmed(self, user_id: str, event_id: str) -> dict | None:
        """Prima registrazione 'confirmed' per la coppia utente/evento, oppure None."""
        for r in self._store.values():
            if (
                r["user_id"] == user_id
                and r["event_id"] == event_id
                and r["status"] == "confirmed"
            ):
                return dict(r)
        return None

    def count_confirmed(self, event_id: str) -> int:
        """Numero di registrazioni 'confirmed' per l'evento."""
        return sum(
            1
            for r in self._store.values()
            if r["event_id"] == event_id and r["status"] == "confirmed"
        )

    def list_all(self, user_id: str | None, event_id: str | None,
                 status: str | None) -> list[dict]:
        """Registrazioni filtrate per user_id/event_id/status (AND logic, filtri opzionali)."""
        result: list[dict] = []
        for r in self._store.values():
            if user_id is not None and r.get("user_id") != user_id:
                continue
            if event_id is not None and r.get("event_id") != event_id:
                continue
            if status is not None and r.get("status") != status:
                continue
            result.append(dict(r))
        return result

    def update(self, registration: dict) -> dict:
        """Sovrascrive la registrazione. Solleva RegistrationNotFoundError se assente."""
        if registration["id"] not in self._store:
            raise RegistrationNotFoundError(
                f"Registration '{registration['id']}' not found"
            )
        self._store[registration["id"]] = dict(registration)
        return dict(registration)

    def delete(self, registration_id: str) -> None:
        """Rimuove la registrazione. Solleva RegistrationNotFoundError se assente."""
        if registration_id not in self._store:
            raise RegistrationNotFoundError(
                f"Registration '{registration_id}' not found"
            )
        del self._store[registration_id]
