import json
import os

from app.repository.base import AbstractEventRepository, EventNotFoundError


class JsonEventRepository(AbstractEventRepository):
    """Backend su file JSON con strategia read-all / write-all."""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        self._path = os.path.join(data_dir, "events.json")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self._path):
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"events": []}, f)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load(self) -> list:
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)["events"]

    def _save(self, events: list) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({"events": events}, f, indent=2)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, event: dict) -> dict:
        """Appende il nuovo evento al file e restituisce una copia."""
        events = self._load()
        events.append(dict(event))
        self._save(events)
        return dict(event)

    def find_by_id(self, event_id: str) -> dict | None:
        """Restituisce una copia dell'evento oppure None se non esiste."""
        for e in self._load():
            if e["id"] == event_id:
                return dict(e)
        return None

    def list_all(self, status: str | None, city: str | None) -> list[dict]:
        """Restituisce tutti gli eventi, opzionalmente filtrati per status e/o city (AND logic)."""
        result: list[dict] = []
        for e in self._load():
            if status is not None and e.get("status") != status:
                continue
            if city is not None and e.get("city") != city:
                continue
            result.append(dict(e))
        return result

    def update(self, event: dict) -> dict:
        """Sostituisce l'evento esistente. Solleva EventNotFoundError se non esiste."""
        events = self._load()
        for idx, e in enumerate(events):
            if e["id"] == event["id"]:
                events[idx] = dict(event)
                self._save(events)
                return dict(event)
        raise EventNotFoundError(f"Event '{event['id']}' not found")

    def delete(self, event_id: str) -> None:
        """Rimuove l'evento. Solleva EventNotFoundError se non esiste."""
        events = self._load()
        filtered = [e for e in events if e["id"] != event_id]
        if len(filtered) == len(events):
            raise EventNotFoundError(f"Event '{event_id}' not found")
        self._save(filtered)
