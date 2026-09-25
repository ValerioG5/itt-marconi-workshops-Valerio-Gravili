from app.repository.base import AbstractEventRepository


class MemoryEventRepository(AbstractEventRepository):
    """Backend in-process. Implementato in T-03."""

    def __init__(self):
        self._store: dict[str, dict] = {}

    def save(self, event: dict) -> dict:
        raise NotImplementedError

    def find_by_id(self, event_id: str) -> dict | None:
        raise NotImplementedError

    def list_all(self, status: str | None, city: str | None) -> list[dict]:
        raise NotImplementedError

    def update(self, event: dict) -> dict:
        raise NotImplementedError

    def delete(self, event_id: str) -> None:
        raise NotImplementedError
