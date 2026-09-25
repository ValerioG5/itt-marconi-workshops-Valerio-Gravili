import os

import pytest

from app.repository.base import UserNotFoundError
from app.repository.json_repo import JsonUserRepository
from app.repository.memory import MemoryUserRepository
from app.repository.sqlite_repo import SqliteUserRepository


# ---------------------------------------------------------------------------
# Fixture parametrizzata: ogni test gira 3 volte (memory, json, sqlite)
# ---------------------------------------------------------------------------


@pytest.fixture(params=["memory", "json", "sqlite"])
def repo(request, tmp_path):
    """Restituisce un repository fresco per ciascun backend."""
    backend = request.param
    if backend == "memory":
        return MemoryUserRepository()
    elif backend == "json":
        return JsonUserRepository(str(tmp_path / "data"))
    else:  # sqlite
        return SqliteUserRepository(str(tmp_path / "data"))


# ---------------------------------------------------------------------------
# Dati di test condivisi
# ---------------------------------------------------------------------------


def _make_user(suffix="1"):
    return {
        "id": f"user-{suffix}",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": f"ada{suffix}@b.com",
        "company": "Engines Ltd",
        "role": "attendee",
        "created_at": "2025-01-01T00:00:00Z",
        "updated_at": "2025-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.req("REQ-USR-P01")
def test_save_and_find_by_id(repo):
    """Salva un utente e lo recupera per id."""
    u = _make_user("1")
    repo.save(u)
    found = repo.find_by_id("user-1")
    assert found is not None
    assert found["id"] == "user-1"
    assert found["email"] == "ada1@b.com"


@pytest.mark.req("REQ-USR-B02")
def test_find_by_email(repo):
    """Trova per email normalizzata (già in minuscolo)."""
    repo.save(_make_user("2"))
    found = repo.find_by_email("ada2@b.com")
    assert found is not None
    assert found["id"] == "user-2"


@pytest.mark.req("REQ-USR-P01")
def test_find_by_email_not_found(repo):
    """find_by_email restituisce None se l'email non esiste."""
    result = repo.find_by_email("nonexistent@x.com")
    assert result is None


@pytest.mark.req("REQ-USR-E02")
def test_list_all_no_filter(repo):
    """list_all senza filtri restituisce tutti gli utenti."""
    repo.save(_make_user("1"))
    repo.save(_make_user("2"))
    all_users = repo.list_all(None, None)
    assert len(all_users) == 2


@pytest.mark.req("REQ-USR-B03")
def test_list_all_filter_role(repo):
    """list_all con filtro role restituisce solo gli utenti con quel role."""
    repo.save(_make_user("1"))  # role=attendee
    org = dict(_make_user("3"), role="organizer")
    repo.save(org)
    filtered = repo.list_all("organizer", None)
    assert len(filtered) == 1
    assert filtered[0]["id"] == "user-3"


@pytest.mark.req("REQ-USR-B03")
def test_list_all_filter_email(repo):
    """list_all con filtro email restituisce solo l'utente con quella email."""
    repo.save(_make_user("1"))
    repo.save(_make_user("2"))
    filtered = repo.list_all(None, "ada1@b.com")
    assert len(filtered) == 1
    assert filtered[0]["id"] == "user-1"


@pytest.mark.req("REQ-USR-E04")
def test_update(repo):
    """update sovrascrive i campi dell'utente e restituisce il dict aggiornato."""
    repo.save(_make_user("1"))
    updated_data = dict(_make_user("1"), role="speaker", updated_at="2025-06-01T00:00:00Z")
    result = repo.update(updated_data)
    assert result["role"] == "speaker"
    # Verifica persistenza: find_by_id deve restituire il dato aggiornato
    found = repo.find_by_id("user-1")
    assert found["role"] == "speaker"


@pytest.mark.req("REQ-USR-E04")
def test_update_not_found(repo):
    """update solleva UserNotFoundError se l'id non esiste."""
    with pytest.raises(UserNotFoundError):
        repo.update(_make_user("999"))


@pytest.mark.req("REQ-USR-E06")
def test_delete(repo):
    """delete rimuove l'utente; find_by_id successivo restituisce None."""
    repo.save(_make_user("1"))
    repo.delete("user-1")
    assert repo.find_by_id("user-1") is None


@pytest.mark.req("REQ-USR-E06")
def test_delete_not_found(repo):
    """delete solleva UserNotFoundError se l'id non esiste."""
    with pytest.raises(UserNotFoundError):
        repo.delete("nonexistent-id")


@pytest.mark.req("REQ-USR-P01")
def test_data_dir_created_automatically(tmp_path):
    """json e sqlite creano DATA_DIR automaticamente se non esiste."""
    new_base = str(tmp_path / "newdir" / "subdir")

    # json
    json_dir = new_base + "/json"
    JsonUserRepository(json_dir)
    assert os.path.isdir(json_dir)

    # sqlite
    sqlite_dir = new_base + "/sqlite"
    SqliteUserRepository(sqlite_dir)
    assert os.path.isdir(sqlite_dir)
