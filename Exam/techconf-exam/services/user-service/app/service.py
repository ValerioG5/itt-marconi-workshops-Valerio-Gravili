import uuid
from datetime import datetime, timezone

from app.repository.base import AbstractUserRepository, UserNotFoundError, EmailAlreadyExistsError


class UserService:
    """Business logic del servizio utenti."""

    def __init__(self, repository: AbstractUserRepository):
        self.repository = repository

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_user(self, data: dict) -> dict:
        """Crea un nuovo utente applicando le regole di business.

        REQ-USR-B02: normalizza email in minuscolo.
        REQ-USR-B01: verifica unicità email.
        REQ-USR-F01: genera id UUID v4 e timestamp ISO 8601.
        """
        email = data["email"].lower()  # REQ-USR-B02

        if self.repository.find_by_email(email):  # REQ-USR-B01
            raise EmailAlreadyExistsError(f"Email '{email}' is already registered")

        now = self._now()
        user_dict = {
            "id": str(uuid.uuid4()),
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "email": email,
            "company": data.get("company", None),
            "role": data.get("role", "attendee"),
            "created_at": now,
            "updated_at": now,
        }
        return self.repository.save(user_dict)

    def get_user(self, user_id: str) -> dict:
        """Recupera un utente per id; solleva UserNotFoundError se assente."""
        result = self.repository.find_by_id(user_id)
        if result is None:
            raise UserNotFoundError(f"User '{user_id}' not found")
        return result

    def list_users(
        self,
        role: str | None,
        email: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict], int]:
        """Restituisce la pagina richiesta e il totale degli utenti.

        REQ-USR-B03: normalizza email se presente (per confronto case-insensitive).
        """
        if email is not None:
            email = email.lower()

        all_items = self.repository.list_all(role, email)
        total = len(all_items)

        start = (page - 1) * page_size
        end = start + page_size
        return all_items[start:end], total

    def replace_user(self, user_id: str, data: dict) -> dict:
        """Sostituzione completa (PUT) di un utente esistente.

        REQ-USR-B02: normalizza email.
        REQ-USR-B01: verifica unicità escludendo l'id corrente.
        REQ-USR-E04: mantiene id e created_at originali; aggiorna updated_at.
        """
        existing = self.repository.find_by_id(user_id)
        if existing is None:
            raise UserNotFoundError(f"User '{user_id}' not found")

        email = data["email"].lower()  # REQ-USR-B02

        existing_by_email = self.repository.find_by_email(email)
        if existing_by_email is not None and existing_by_email["id"] != user_id:
            raise EmailAlreadyExistsError(f"Email '{email}' is already registered")

        user_dict = {
            "id": existing["id"],
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "email": email,
            "company": data.get("company", None),
            "role": data.get("role", "attendee"),
            "created_at": existing["created_at"],
            "updated_at": self._now(),
        }
        return self.repository.update(user_dict)

    def update_user(self, user_id: str, data: dict) -> dict:
        """Aggiornamento parziale (PATCH) di un utente esistente.

        REQ-USR-B02: normalizza email se presente.
        REQ-USR-B01: verifica unicità email escludendo l'id corrente.
        REQ-USR-E05: aggiorna solo i campi presenti in data.
        """
        existing = self.repository.find_by_id(user_id)
        if existing is None:
            raise UserNotFoundError(f"User '{user_id}' not found")

        updated = dict(existing)

        if "email" in data:
            email = data["email"].lower()  # REQ-USR-B02
            existing_by_email = self.repository.find_by_email(email)
            if existing_by_email is not None and existing_by_email["id"] != user_id:
                raise EmailAlreadyExistsError(f"Email '{email}' is already registered")
            updated["email"] = email

        # Applica solo i campi presenti in data (esclusa email già gestita)
        for field in ("first_name", "last_name", "company", "role"):
            if field in data:
                updated[field] = data[field]

        updated["updated_at"] = self._now()
        return self.repository.update(updated)

    def delete_user(self, user_id: str) -> None:
        """Elimina un utente; propaga UserNotFoundError se non esiste."""
        self.repository.delete(user_id)
