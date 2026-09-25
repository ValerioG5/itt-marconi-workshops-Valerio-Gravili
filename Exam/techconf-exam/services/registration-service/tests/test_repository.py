"""T-12 — Test unitari dei tre backend di persistenza.

La fixture `repo` è parametrizzata su memory/json/sqlite: ogni test gira tre
volte, così le tre implementazioni restano osservabilmente equivalenti.
I test sulla capienza sono i più importanti del file: `count_confirmed` e
`find_confirmed` sono i due metodi su cui poggiano REQ-REG-B04 e REQ-REG-B05.
"""

import os

import pytest

from app.repository.base import RegistrationNotFoundError
from app.repository.json_repo import JsonRegistrationRepository
from app.repository.memory import MemoryRegistrationRepository
from app.repository.sqlite_repo import SqliteRegistrationRepository


def _reg(i, user="u1", event="e1", status="confirmed", amount=149.0):
    """Registrazione con le 7 chiavi del dominio."""
    return {
        "id": f"reg-{i}",
        "user_id": user,
        "event_id": event,
        "amount": amount,
        "status": status,
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


@pytest.fixture(params=["memory", "json", "sqlite"])
def repo(request, tmp_path):
    if request.param == "memory":
        return MemoryRegistrationRepository()
    if request.param == "json":
        return JsonRegistrationRepository(str(tmp_path / "json_data"))
    return SqliteRegistrationRepository(str(tmp_path / "sqlite_data"))


# -----------------------------------------------------------------------
# CRUD
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-P01")
def test_save_and_find_by_id(repo):
    saved = repo.save(_reg(1))

    assert saved["id"] == "reg-1"
    found = repo.find_by_id("reg-1")
    assert found == _reg(1)


@pytest.mark.req("REQ-REG-P01")
def test_find_by_id_not_found(repo):
    assert repo.find_by_id("missing") is None


@pytest.mark.req("REQ-REG-P01")
def test_list_all_no_filter(repo):
    repo.save(_reg(1))
    repo.save(_reg(2, user="u2"))

    assert len(repo.list_all(None, None, None)) == 2


@pytest.mark.req("REQ-REG-P01")
def test_list_all_filter_user(repo):
    repo.save(_reg(1, user="u1"))
    repo.save(_reg(2, user="u2"))

    items = repo.list_all("u1", None, None)

    assert [r["id"] for r in items] == ["reg-1"]


@pytest.mark.req("REQ-REG-P01")
def test_list_all_filter_event(repo):
    repo.save(_reg(1, event="e1"))
    repo.save(_reg(2, event="e2"))

    items = repo.list_all(None, "e2", None)

    assert [r["id"] for r in items] == ["reg-2"]


@pytest.mark.req("REQ-REG-P01")
def test_list_all_filter_status(repo):
    repo.save(_reg(1, status="confirmed"))
    repo.save(_reg(2, status="cancelled"))

    items = repo.list_all(None, None, "cancelled")

    assert [r["id"] for r in items] == ["reg-2"]


@pytest.mark.req("REQ-REG-P01")
def test_list_all_filter_combined(repo):
    repo.save(_reg(1, user="u1", event="e1", status="confirmed"))
    repo.save(_reg(2, user="u1", event="e1", status="cancelled"))
    repo.save(_reg(3, user="u2", event="e1", status="confirmed"))

    items = repo.list_all("u1", "e1", "confirmed")

    assert [r["id"] for r in items] == ["reg-1"]


@pytest.mark.req("REQ-REG-P01")
def test_update(repo):
    repo.save(_reg(1))
    updated = dict(_reg(1), status="cancelled", updated_at="2025-02-02T00:00:00Z")

    returned = repo.update(updated)

    assert returned["status"] == "cancelled"
    assert repo.find_by_id("reg-1")["status"] == "cancelled"
    assert repo.find_by_id("reg-1")["updated_at"] == "2025-02-02T00:00:00Z"


@pytest.mark.req("REQ-REG-P01")
def test_update_not_found(repo):
    with pytest.raises(RegistrationNotFoundError):
        repo.update(_reg(99))


@pytest.mark.req("REQ-REG-P01")
def test_delete(repo):
    repo.save(_reg(1))

    repo.delete("reg-1")

    assert repo.find_by_id("reg-1") is None


@pytest.mark.req("REQ-REG-P01")
def test_delete_not_found(repo):
    with pytest.raises(RegistrationNotFoundError):
        repo.delete("missing")


@pytest.mark.req("REQ-REG-P01")
def test_data_dir_created_automatically(tmp_path):
    """I backend su disco creano DATA_DIR se assente (REQ-REG-P01 criterio 5)."""
    json_dir = tmp_path / "nested" / "json"
    sqlite_dir = tmp_path / "nested" / "sqlite"

    JsonRegistrationRepository(str(json_dir))
    SqliteRegistrationRepository(str(sqlite_dir))

    assert os.path.isdir(json_dir)
    assert os.path.isfile(os.path.join(str(json_dir), "registrations.json"))
    assert os.path.isdir(sqlite_dir)
    assert os.path.isfile(os.path.join(str(sqlite_dir), "registrations.db"))


# -----------------------------------------------------------------------
# Capienza: count_confirmed / find_confirmed
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B05")
def test_count_confirmed_counts_only_confirmed(repo):
    repo.save(_reg(1, user="u1", event="e1", status="confirmed"))
    repo.save(_reg(2, user="u2", event="e1", status="confirmed"))
    repo.save(_reg(3, user="u3", event="e1", status="cancelled"))

    assert repo.count_confirmed("e1") == 2


@pytest.mark.req("REQ-REG-B07")
def test_count_confirmed_decreases_after_cancel(repo):
    repo.save(_reg(1, user="u1", event="e1"))
    repo.save(_reg(2, user="u2", event="e1"))
    assert repo.count_confirmed("e1") == 2

    repo.update(dict(_reg(1, user="u1", event="e1"), status="cancelled"))

    assert repo.count_confirmed("e1") == 1


@pytest.mark.req("REQ-REG-B05")
def test_count_confirmed_isolated_per_event(repo):
    repo.save(_reg(1, user="u1", event="e1"))
    repo.save(_reg(2, user="u1", event="e2"))
    repo.save(_reg(3, user="u2", event="e2"))

    assert repo.count_confirmed("e1") == 1
    assert repo.count_confirmed("e2") == 2


@pytest.mark.req("REQ-REG-B05")
def test_count_confirmed_zero_for_unknown_event(repo):
    repo.save(_reg(1, event="e1"))

    assert repo.count_confirmed("does-not-exist") == 0


@pytest.mark.req("REQ-REG-B04")
def test_find_confirmed_ignores_cancelled(repo):
    repo.save(_reg(1, user="u1", event="e1", status="cancelled"))

    assert repo.find_confirmed("u1", "e1") is None


@pytest.mark.req("REQ-REG-B04")
def test_find_confirmed_returns_none_for_other_user(repo):
    repo.save(_reg(1, user="u1", event="e1", status="confirmed"))

    assert repo.find_confirmed("u1", "e1")["id"] == "reg-1"
    assert repo.find_confirmed("u2", "e1") is None
    assert repo.find_confirmed("u1", "e2") is None


@pytest.mark.req("REQ-REG-B04")
def test_save_two_rows_same_pair_when_first_cancelled(repo):
    """Re-iscrizione dopo cancellazione: due righe con la stessa coppia devono
    poter coesistere se una sola è 'confirmed'. Su SQLite un UNIQUE non
    condizionato su (user_id, event_id) romperebbe qui.
    """
    repo.save(_reg(1, user="u1", event="e1", status="cancelled"))
    repo.save(_reg(2, user="u1", event="e1", status="confirmed"))

    assert repo.count_confirmed("e1") == 1
    assert repo.find_confirmed("u1", "e1")["id"] == "reg-2"
    assert len(repo.list_all("u1", "e1", None)) == 2
