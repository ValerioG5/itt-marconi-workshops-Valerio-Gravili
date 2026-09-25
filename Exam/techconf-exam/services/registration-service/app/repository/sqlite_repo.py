import os
import sqlite3

from app.repository.base import (
    AbstractRegistrationRepository,
    RegistrationNotFoundError,
)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS registrations (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    event_id   TEXT NOT NULL,
    amount     REAL NOT NULL,
    status     TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

# Coppia esatta interrogata da count_confirmed e find_confirmed.
_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_registrations_event_status
    ON registrations (event_id, status);
"""

# Indice unico PARZIALE: difesa in profondità sul duplicato, senza rompere
# la re-iscrizione dopo cancellazione (esistono legittimamente due righe con
# la stessa coppia se una è 'cancelled').
_CREATE_UNIQUE_INDEX = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_registrations_confirmed
    ON registrations (user_id, event_id) WHERE status = 'confirmed';
"""

_COLUMNS = (
    "id",
    "user_id",
    "event_id",
    "amount",
    "status",
    "created_at",
    "updated_at",
)


class SqliteRegistrationRepository(AbstractRegistrationRepository):
    """Backend su SQLite: connessione aperta e chiusa per ogni operazione."""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        self._db_path = os.path.join(data_dir, "registrations.db")
        os.makedirs(data_dir, exist_ok=True)
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(_CREATE_TABLE)
            cursor.execute(_CREATE_INDEX)
            cursor.execute(_CREATE_UNIQUE_INDEX)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Converte la tupla restituita da SELECT * nel dict registrazione a 7 chiavi."""
        return dict(zip(_COLUMNS, row))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, registration: dict) -> dict:
        """Inserisce una nuova registrazione nel database."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO registrations "
                "(id, user_id, event_id, amount, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    registration["id"],
                    registration["user_id"],
                    registration["event_id"],
                    registration["amount"],
                    registration["status"],
                    registration["created_at"],
                    registration["updated_at"],
                ),
            )
            conn.commit()
            return dict(registration)
        finally:
            conn.close()

    def find_by_id(self, registration_id: str) -> dict | None:
        """Restituisce il dict registrazione oppure None se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM registrations WHERE id = ?", (registration_id,)
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row is not None else None
        finally:
            conn.close()

    def find_confirmed(self, user_id: str, event_id: str) -> dict | None:
        """Prima registrazione 'confirmed' per la coppia utente/evento, oppure None."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM registrations "
                "WHERE user_id = ? AND event_id = ? AND status = 'confirmed'",
                (user_id, event_id),
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row is not None else None
        finally:
            conn.close()

    def count_confirmed(self, event_id: str) -> int:
        """Numero di registrazioni 'confirmed' per l'evento, contate dal database."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM registrations "
                "WHERE event_id = ? AND status = 'confirmed'",
                (event_id,),
            )
            return int(cursor.fetchone()[0])
        finally:
            conn.close()

    def list_all(self, user_id: str | None, event_id: str | None,
                 status: str | None) -> list[dict]:
        """Registrazioni filtrate per user_id/event_id/status (AND logic, filtri opzionali)."""
        query = "SELECT * FROM registrations"
        params: list = []
        conditions: list[str] = []

        if user_id is not None:
            conditions.append("user_id = ?")
            params.append(user_id)
        if event_id is not None:
            conditions.append("event_id = ?")
            params.append(event_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update(self, registration: dict) -> dict:
        """Sovrascrive i campi mutabili. Solleva RegistrationNotFoundError se assente."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE registrations SET user_id=?, event_id=?, amount=?, status=?, "
                "updated_at=? WHERE id=?",
                (
                    registration["user_id"],
                    registration["event_id"],
                    registration["amount"],
                    registration["status"],
                    registration["updated_at"],
                    registration["id"],
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise RegistrationNotFoundError(
                    f"Registration '{registration['id']}' not found"
                )
            return dict(registration)
        finally:
            conn.close()

    def delete(self, registration_id: str) -> None:
        """Rimuove la registrazione. Solleva RegistrationNotFoundError se assente."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM registrations WHERE id = ?", (registration_id,)
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise RegistrationNotFoundError(
                    f"Registration '{registration_id}' not found"
                )
        finally:
            conn.close()
