import os
import sqlite3

from app.repository.base import AbstractUserRepository, UserNotFoundError

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    company     TEXT,
    role        TEXT NOT NULL DEFAULT 'attendee',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
"""


class SqliteUserRepository(AbstractUserRepository):
    """Implementazione SQLite su disco del repository utenti."""

    def __init__(self, data_dir: str):
        self._db_path = os.path.join(data_dir, "users.db")
        os.makedirs(data_dir, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(_CREATE_TABLE)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Converte una tupla (id, first_name, last_name, email, company, role, created_at, updated_at) in dict."""
        keys = ("id", "first_name", "last_name", "email", "company", "role", "created_at", "updated_at")
        return dict(zip(keys, row))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, user: dict) -> dict:
        """Inserisce un nuovo utente nel database."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (id, first_name, last_name, email, company, role, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    user["id"],
                    user["first_name"],
                    user["last_name"],
                    user["email"],
                    user.get("company"),
                    user["role"],
                    user["created_at"],
                    user["updated_at"],
                ),
            )
            conn.commit()
            return dict(user)
        finally:
            conn.close()

    def find_by_id(self, user_id: str) -> dict | None:
        """Restituisce il dict utente oppure None se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row is not None else None
        finally:
            conn.close()

    def find_by_email(self, email: str) -> dict | None:
        """Ricerca per email (già normalizzata). Restituisce None se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row is not None else None
        finally:
            conn.close()

    def list_all(self, role: str | None, email: str | None) -> list[dict]:
        """Restituisce tutti gli utenti, opzionalmente filtrati per role e/o email."""
        query = "SELECT * FROM users"
        params: list = []
        conditions: list[str] = []

        if role is not None:
            conditions.append("role = ?")
            params.append(role)
        if email is not None:
            conditions.append("email = ?")
            params.append(email)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update(self, user: dict) -> dict:
        """Sovrascrive i campi mutabili dell'utente. Solleva UserNotFoundError se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE users SET first_name=?, last_name=?, email=?, company=?, role=?, updated_at=? WHERE id=?",
                (
                    user["first_name"],
                    user["last_name"],
                    user["email"],
                    user.get("company"),
                    user["role"],
                    user["updated_at"],
                    user["id"],
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise UserNotFoundError(f"User '{user['id']}' not found")
            return dict(user)
        finally:
            conn.close()

    def delete(self, user_id: str) -> None:
        """Rimuove l'utente. Solleva UserNotFoundError se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise UserNotFoundError(f"User '{user_id}' not found")
        finally:
            conn.close()
