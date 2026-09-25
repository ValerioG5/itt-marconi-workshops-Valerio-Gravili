from app.repository.base import AbstractUserRepository, UserNotFoundError


class MemoryUserRepository(AbstractUserRepository):
    """Implementazione in-memory del repository utenti."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def save(self, user: dict) -> dict:
        """Inserisce user nello store con chiave user["id"]; restituisce una copia."""
        self._store[user["id"]] = dict(user)
        return dict(user)

    def find_by_id(self, user_id: str) -> dict | None:
        """Restituisce una copia del dict utente o None se non esiste."""
        result = self._store.get(user_id)
        return dict(result) if result is not None else None

    def find_by_email(self, email: str) -> dict | None:
        """Itera i valori e restituisce il primo con email corrispondente, o None."""
        for u in self._store.values():
            if u["email"] == email:
                return dict(u)
        return None

    def list_all(self, role: str | None, email: str | None) -> list[dict]:
        """Restituisce lista filtrata per role e/o email (AND logic); se entrambi None restituisce tutti."""
        result = []
        for u in self._store.values():
            if role is not None and u.get("role") != role:
                continue
            if email is not None and u.get("email") != email:
                continue
            result.append(dict(u))
        return result

    def update(self, user: dict) -> dict:
        """Sovrascrive l'utente esistente; solleva UserNotFoundError se non esiste."""
        if user["id"] not in self._store:
            raise UserNotFoundError(f"User '{user['id']}' not found")
        self._store[user["id"]] = dict(user)
        return dict(user)

    def delete(self, user_id: str) -> None:
        """Rimuove l'utente; solleva UserNotFoundError se non esiste."""
        if user_id not in self._store:
            raise UserNotFoundError(f"User '{user_id}' not found")
        del self._store[user_id]
