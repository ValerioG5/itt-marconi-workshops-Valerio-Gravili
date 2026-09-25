import json
import os

from app.repository.base import AbstractUserRepository, UserNotFoundError


class JsonUserRepository(AbstractUserRepository):
    """Implementazione JSON su disco del repository utenti."""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        self._path = os.path.join(data_dir, "users.json")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self._path):
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump({"users": []}, f)

    def _load(self) -> list:
        with open(self._path, "r", encoding="utf-8") as f:
            return json.load(f)["users"]

    def _save(self, users: list) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump({"users": users}, f, indent=2)

    def save(self, user: dict) -> dict:
        users = self._load()
        users.append(dict(user))
        self._save(users)
        return dict(user)

    def find_by_id(self, user_id: str) -> dict | None:
        for u in self._load():
            if u["id"] == user_id:
                return dict(u)
        return None

    def find_by_email(self, email: str) -> dict | None:
        for u in self._load():
            if u["email"] == email:
                return dict(u)
        return None

    def list_all(self, role: str | None, email: str | None) -> list[dict]:
        result = []
        for u in self._load():
            if role is not None and u.get("role") != role:
                continue
            if email is not None and u.get("email") != email:
                continue
            result.append(dict(u))
        return result

    def update(self, user: dict) -> dict:
        users = self._load()
        for idx, u in enumerate(users):
            if u["id"] == user["id"]:
                users[idx] = dict(user)
                self._save(users)
                return dict(user)
        raise UserNotFoundError(f"User '{user['id']}' not found")

    def delete(self, user_id: str) -> None:
        users = self._load()
        filtered = [u for u in users if u["id"] != user_id]
        if len(filtered) == len(users):
            raise UserNotFoundError(f"User '{user_id}' not found")
        self._save(filtered)
