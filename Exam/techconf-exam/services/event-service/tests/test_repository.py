"""T-12 — Test unitari sui tre backend di persistenza.

Ogni test gira tre volte (memory, json, sqlite) grazie alla fixture
parametrizzata: è il modo più diretto di verificare REQ-EVT-P01 criterio 4,
cioè che i backend siano davvero interscambiabili a parità di comportamento.
"""

import os

import pytest

from app.repository.base import EventNotFoundError
from app.repository.json_repo import JsonEventRepository
from app.repository.memory import MemoryEventRepository
from app.repository.sqlite_repo import SqliteEventRepository


@pytest.fixture(params=["memory", "json", "sqlite"])
def repo(request, tmp_path):
    """Un repository pulito per ogni backend; json e sqlite scrivono in tmp_path."""
    if request.param == "memory":
        return MemoryEventRepository()
    if request.param == "json":
        return JsonEventRepository(str(tmp_path / "json_data"))
    return SqliteEventRepository(str(tmp_path / "sqlite_data"))


def _event(i, status="draft", city="Roma"):
    """Costruisce un evento completo con tutte e 13 le chiavi dello schema."""
    return {
        "id": f"evt-{i}",
        "title": f"PyConf Italia {i}",
        "description": None,
        "organizer_id": "org1",
        "venue": "Auditorium",
        "city": city,
        "start_date": "2026-10-15",
        "end_date": "2026-10-16",
        "capacity": 100,
        "price": 149.00,
        "status": status,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# save / find_by_id
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-P01")
def test_save_and_find_by_id(repo):
    saved = repo.save(_event(1))
    assert saved["id"] == "evt-1"

    found = repo.find_by_id("evt-1")
    assert found is not None
    assert found["title"] == "PyConf Italia 1"
    assert found["capacity"] == 100
    assert found["status"] == "draft"


@pytest.mark.req("REQ-EVT-E03")
def test_find_by_id_not_found(repo):
    assert repo.find_by_id("missing") is None


# ---------------------------------------------------------------------------
# list_all e filtri
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E02")
def test_list_all_no_filter(repo):
    repo.save(_event(1))
    repo.save(_event(2))

    items = repo.list_all(None, None)
    assert len(items) == 2
    assert {e["id"] for e in items} == {"evt-1", "evt-2"}


@pytest.mark.req("REQ-EVT-B06")
def test_list_all_filter_status(repo):
    repo.save(_event(1, status="draft"))
    repo.save(_event(2, status="published"))

    items = repo.list_all("published", None)
    assert [e["id"] for e in items] == ["evt-2"]


@pytest.mark.req("REQ-EVT-B06")
def test_list_all_filter_city(repo):
    repo.save(_event(1, city="Roma"))
    repo.save(_event(2, city="Milano"))

    items = repo.list_all(None, "Milano")
    assert [e["id"] for e in items] == ["evt-2"]


@pytest.mark.req("REQ-EVT-B06")
def test_list_all_filter_both(repo):
    repo.save(_event(1, status="draft", city="Roma"))
    repo.save(_event(2, status="published", city="Roma"))
    repo.save(_event(3, status="published", city="Milano"))

    items = repo.list_all("published", "Roma")
    assert [e["id"] for e in items] == ["evt-2"]


@pytest.mark.req("REQ-EVT-B06")
def test_list_all_filter_both_no_match(repo):
    repo.save(_event(1, status="draft", city="Roma"))

    assert repo.list_all("published", "Milano") == []


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E04")
def test_update(repo):
    repo.save(_event(1))

    modified = _event(1)
    modified["title"] = "PyConf Italia 2026"
    modified["status"] = "published"
    modified["updated_at"] = "2025-06-01T12:00:00Z"
    repo.update(modified)

    found = repo.find_by_id("evt-1")
    assert found["title"] == "PyConf Italia 2026"
    assert found["status"] == "published"
    assert found["updated_at"] == "2025-06-01T12:00:00Z"
    # criterio 7: created_at resta quello originale
    assert found["created_at"] == "2025-01-01T00:00:00Z"


@pytest.mark.req("REQ-EVT-E04")
def test_update_not_found(repo):
    with pytest.raises(EventNotFoundError):
        repo.update(_event(99))


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E06")
def test_delete(repo):
    repo.save(_event(1))
    repo.delete("evt-1")
    assert repo.find_by_id("evt-1") is None


@pytest.mark.req("REQ-EVT-E06")
def test_delete_not_found(repo):
    with pytest.raises(EventNotFoundError):
        repo.delete("missing")


# ---------------------------------------------------------------------------
# REQ-EVT-P01 criterio 5 — creazione automatica di DATA_DIR
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-P01")
def test_data_dir_created_automatically(tmp_path):
    """I backend su disco creano DATA_DIR se non esiste (anche annidato)."""
    json_dir = tmp_path / "nested" / "json_dir"
    sqlite_dir = tmp_path / "nested" / "sqlite_dir"
    assert not os.path.isdir(str(json_dir))
    assert not os.path.isdir(str(sqlite_dir))

    JsonEventRepository(str(json_dir))
    SqliteEventRepository(str(sqlite_dir))

    assert os.path.isdir(str(json_dir))
    assert os.path.isfile(str(json_dir / "events.json"))
    assert os.path.isdir(str(sqlite_dir))
    assert os.path.isfile(str(sqlite_dir / "events.db"))
