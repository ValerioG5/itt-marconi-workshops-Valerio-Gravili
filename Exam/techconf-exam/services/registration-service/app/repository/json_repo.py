import json
import os

from app.repository.base import (
    AbstractRegistrationRepository,
    RegistrationNotFoundError,
)


class JsonRegistrationRepository(AbstractRegistrationRepository):
    """Backend su file JSON con strategia read-all / write-all."""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        self._path = os.path.join(data_dir, "registrations.json")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self._path):
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"registrations": []}, f)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load(self) -> list:
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)["registrations"]

    def _save(self, registrations: list) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({"registrations": registrations}, f, indent=2)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, registration: dict) -> dict:
        """Appende la nuova registrazione al file e restituisce una copia."""
        registrations = self._load()
        registrations.append(dict(registration))
        self._save(registrations)
        return dict(registration)

    def find_by_id(self, registration_id: str) -> dict | None:
        """Restituisce una copia della registrazione oppure None se non esiste."""
        for r in self._load():
            if r["id"] == registration_id:
                return dict(r)
        return None

    def find_confirmed(self, user_id: str, event_id: str) -> dict | None:
        """Prima registrazione 'confirmed' per la coppia utente/evento, oppure None."""
        for r in self._load():
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
            for r in self._load()
            if r["event_id"] == event_id and r["status"] == "confirmed"
        )

    def list_all(self, user_id: str | None, event_id: str | None,
                 status: str | None) -> list[dict]:
        """Registrazioni filtrate per user_id/event_id/status (AND logic, filtri opzionali)."""
        result: list[dict] = []
        for r in self._load():
            if user_id is not None and r.get("user_id") != user_id:
                continue
            if event_id is not None and r.get("event_id") != event_id:
                continue
            if status is not None and r.get("status") != status:
                continue
            result.append(dict(r))
        return result

    def update(self, registration: dict) -> dict:
        """Sostituisce la registrazione. Solleva RegistrationNotFoundError se assente."""
        registrations = self._load()
        for idx, r in enumerate(registrations):
            if r["id"] == registration["id"]:
                registrations[idx] = dict(registration)
                self._save(registrations)
                return dict(registration)
        raise RegistrationNotFoundError(
            f"Registration '{registration['id']}' not found"
        )

    def delete(self, registration_id: str) -> None:
        """Rimuove la registrazione. Solleva RegistrationNotFoundError se assente."""
        registrations = self._load()
        filtered = [r for r in registrations if r["id"] != registration_id]
        if len(filtered) == len(registrations):
            raise RegistrationNotFoundError(
                f"Registration '{registration_id}' not found"
            )
        self._save(filtered)
