from app.repository.base import AbstractEventRepository


class JsonEventRepository(AbstractEventRepository):
    """Backend su file JSON. Implementato in T-04."""

    def __init__(self, data_dir):
        self._data_dir = data_dir

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
