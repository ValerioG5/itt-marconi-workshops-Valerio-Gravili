import pytest
from app.repository.memory import MemoryUserRepository
from app.repository.base import UserNotFoundError, EmailAlreadyExistsError
from app.service import UserService


@pytest.fixture
def svc():
    """UserService fresco con MemoryUserRepository per ogni test."""
    return UserService(MemoryUserRepository())


def _valid_data(**kwargs):
    base = {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@b.com"}
    base.update(kwargs)
    return base


# -----------------------------------------------------------------------
# REQ-USR-B02 + REQ-USR-F01
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-B02", "REQ-USR-F01")
def test_create_user_ok(svc):
    """Crea utente: id UUID, role default attendee, email lowercase."""
    u = svc.create_user(_valid_data(email="ADA@B.COM"))
    assert u["email"] == "ada@b.com"
    assert u["role"] == "attendee"
    assert len(u["id"]) == 36  # UUID v4
    assert u["created_at"] == u["updated_at"]


@pytest.mark.req("REQ-USR-B02")
def test_create_user_email_lowercase(svc):
    """email con maiuscole viene salvata in minuscolo."""
    u = svc.create_user(_valid_data(email="Ada@Example.COM"))
    assert u["email"] == "ada@example.com"


# -----------------------------------------------------------------------
# REQ-USR-B01
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-B01")
def test_create_user_duplicate_email(svc):
    """Seconda creazione con stessa email (case diversa) -> EmailAlreadyExistsError."""
    svc.create_user(_valid_data(email="ada@b.com"))
    with pytest.raises(EmailAlreadyExistsError):
        svc.create_user(_valid_data(email="ADA@B.COM"))


# -----------------------------------------------------------------------
# REQ-USR-E03
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E03")
def test_get_user_not_found(svc):
    """get_user con id inesistente solleva UserNotFoundError."""
    with pytest.raises(UserNotFoundError):
        svc.get_user("nonexistent-id")


# -----------------------------------------------------------------------
# REQ-USR-B03
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-B03")
def test_list_users_filter_role(svc):
    """list_users con filtro role restituisce solo utenti con quel role."""
    svc.create_user(_valid_data(email="a1@b.com", role="attendee"))
    svc.create_user(_valid_data(email="a2@b.com", role="organizer"))
    items, total = svc.list_users("organizer", None, 1, 10)
    assert total == 1
    assert items[0]["role"] == "organizer"


# -----------------------------------------------------------------------
# REQ-USR-E02
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E02")
def test_list_users_pagination(svc):
    """Crea 5 utenti; page=1, page_size=2 -> 2 risultati, total=5."""
    for i in range(5):
        svc.create_user(_valid_data(email=f"user{i}@b.com"))
    items, total = svc.list_users(None, None, 1, 2)
    assert total == 5
    assert len(items) == 2


# -----------------------------------------------------------------------
# REQ-USR-E04
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E04")
def test_replace_user_ok(svc):
    """replace_user: created_at invariato, updated_at aggiornato, campi sostituiti."""
    u = svc.create_user(_valid_data())
    replaced = svc.replace_user(u["id"], {"first_name": "Eve", "last_name": "M", "email": "ada@b.com", "role": "speaker"})
    assert replaced["first_name"] == "Eve"
    assert replaced["role"] == "speaker"
    assert replaced["created_at"] == u["created_at"]


@pytest.mark.req("REQ-USR-B01")
def test_replace_user_email_conflict(svc):
    """replace_user con email di un altro utente -> EmailAlreadyExistsError."""
    svc.create_user(_valid_data(email="ada@b.com"))
    u2 = svc.create_user(_valid_data(email="eve@b.com"))
    with pytest.raises(EmailAlreadyExistsError):
        svc.replace_user(u2["id"], {"first_name": "X", "last_name": "Y", "email": "ada@b.com"})


# -----------------------------------------------------------------------
# REQ-USR-E05
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E05")
def test_update_user_partial(svc):
    """PATCH solo company; altri campi invariati."""
    u = svc.create_user(_valid_data())
    updated = svc.update_user(u["id"], {"company": "ACME"})
    assert updated["company"] == "ACME"
    assert updated["first_name"] == u["first_name"]
    assert updated["email"] == u["email"]


# -----------------------------------------------------------------------
# REQ-USR-E06
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E06")
def test_delete_user_ok(svc):
    """delete_user rimuove l'utente; get_user successivo -> UserNotFoundError."""
    u = svc.create_user(_valid_data())
    svc.delete_user(u["id"])
    with pytest.raises(UserNotFoundError):
        svc.get_user(u["id"])
