from app.repository.base import AbstractEventRepository, EventNotFoundError


class MemoryEventRepository(AbstractEventRepository):
    """Backend in-process basato su dizionario."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def save(self, event: dict) -> dict:
        """Inserisce un nuovo evento nello store in memoria."""
        self._store[event["id"]] = dict(event)
        return dict(event)

    def find_by_id(self, event_id: str) -> dict | None:
        """Restituisce una copia dell'evento oppure None se non esiste."""
        event = self._store.get(event_id)
        return dict(event) if event is not None else None

    def list_all(self, status: str | None, city: str | None) -> list[dict]:
        """Restituisce tutti gli eventi, opzionalmente filtrati per status e/o city (AND logic)."""
        result: list[dict] = []
        for e in self._store.values():
            if status is not None and e.get("status") != status:
                continue
            if city is not None and e.get("city") != city:
                continue
            result.append(dict(e))
        return result

    def update(self, event: dict) -> dict:
        """Sovrascrive l'evento esistente. Solleva EventNotFoundError se non esiste."""
        if event["id"] not in self._store:
            raise EventNotFoundError(f"Event '{event['id']}' not found")
        self._store[event["id"]] = dict(event)
        return dict(event)

    def delete(self, event_id: str) -> None:
        """Rimuove l'evento. Solleva EventNotFoundError se non esiste."""
        if event_id not in self._store:
            raise EventNotFoundError(f"Event '{event_id}' not found")
        del self._store[event_id]
