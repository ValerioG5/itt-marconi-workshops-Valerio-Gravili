from app.repository.base import AbstractUserRepository


class JsonUserRepository(AbstractUserRepository):
    """Implementazione JSON su disco (stub). I metodi vengono implementati nel task T-04."""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir

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
