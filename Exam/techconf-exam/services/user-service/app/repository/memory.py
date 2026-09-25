from app.repository.base import AbstractUserRepository


class MemoryUserRepository(AbstractUserRepository):
    """Implementazione in-memory (stub). I metodi vengono implementati nel task T-03."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def save(self, user: dict) -> dict:
        raise NotImplementedError

    def find_by_id(self, user_id: str) -> dict | None:
        raise NotImplementedError

    def find_by_email(self, email: str) -> dict | None:
        raise NotImplementedError

    def list_all(self, role: str | None, email: str | None) -> list[dict]:
        raise NotImplementedError

    def update(self, user: dict) -> dict:
        raise NotImplementedError

    def delete(self, user_id: str) -> None:
        raise NotImplementedError
