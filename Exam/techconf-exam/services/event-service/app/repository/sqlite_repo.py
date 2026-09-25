import os
import sqlite3

from app.repository.base import AbstractEventRepository, EventNotFoundError

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    title        TEXT    NOT NULL,
    description  TEXT,
    organizer_id TEXT    NOT NULL,
    venue        TEXT    NOT NULL,
    city         TEXT    NOT NULL,
    start_date   TEXT    NOT NULL,
    end_date     TEXT    NOT NULL,
    capacity     INTEGER NOT NULL,
    price        REAL    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'draft',
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);
"""

_COLUMNS = (
    "id",
    "title",
    "description",
    "organizer_id",
    "venue",
    "city",
    "start_date",
    "end_date",
    "capacity",
    "price",
    "status",
    "created_at",
    "updated_at",
)


class SqliteEventRepository(AbstractEventRepository):
    """Backend su SQLite: connessione aperta e chiusa per ogni operazione."""

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        self._db_path = os.path.join(data_dir, "events.db")
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
        """Converte la tupla restituita da SELECT * nel dict evento con 13 chiavi."""
        return dict(zip(_COLUMNS, row))

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def save(self, event: dict) -> dict:
        """Inserisce un nuovo evento nel database."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO events (id, title, description, organizer_id, venue, city, "
                "start_date, end_date, capacity, price, status, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event["id"],
                    event["title"],
                    event.get("description"),
                    event["organizer_id"],
                    event["venue"],
                    event["city"],
                    event["start_date"],
                    event["end_date"],
                    event["capacity"],
                    event["price"],
                    event["status"],
                    event["created_at"],
                    event["updated_at"],
                ),
            )
            conn.commit()
            return dict(event)
        finally:
            conn.close()

    def find_by_id(self, event_id: str) -> dict | None:
        """Restituisce il dict evento oppure None se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
            row = cursor.fetchone()
            return self._row_to_dict(row) if row is not None else None
        finally:
            conn.close()

    def list_all(self, status: str | None, city: str | None) -> list[dict]:
        """Restituisce tutti gli eventi, opzionalmente filtrati per status e/o city (AND logic)."""
        query = "SELECT * FROM events"
        params: list = []
        conditions: list[str] = []

        if status is not None:
            conditions.append("status = ?")
            params.append(status)
        if city is not None:
            conditions.append("city = ?")
            params.append(city)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def update(self, event: dict) -> dict:
        """Sovrascrive i campi mutabili dell'evento. Solleva EventNotFoundError se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE events SET title=?, description=?, organizer_id=?, venue=?, city=?, "
                "start_date=?, end_date=?, capacity=?, price=?, status=?, updated_at=? WHERE id=?",
                (
                    event["title"],
                    event.get("description"),
                    event["organizer_id"],
                    event["venue"],
                    event["city"],
                    event["start_date"],
                    event["end_date"],
                    event["capacity"],
                    event["price"],
                    event["status"],
                    event["updated_at"],
                    event["id"],
                ),
            )
            conn.commit()
            if cursor.rowcount == 0:
                raise EventNotFoundError(f"Event '{event['id']}' not found")
            return dict(event)
        finally:
            conn.close()

    def delete(self, event_id: str) -> None:
        """Rimuove l'evento. Solleva EventNotFoundError se non esiste."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
            conn.commit()
            if cursor.rowcount == 0:
                raise EventNotFoundError(f"Event '{event_id}' not found")
        finally:
            conn.close()
