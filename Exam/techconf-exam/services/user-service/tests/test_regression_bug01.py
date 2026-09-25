"""Regression test per BUG-01.

`UserService._now()` usava `datetime.utcnow()`, deprecato da Python 3.12 e
"scheduled for removal": alla rimozione il servizio si romperebbe del tutto.
event-service e registration-service usavano già `datetime.now(timezone.utc)`.

Il test fallisce sul codice non corretto perché trasforma il DeprecationWarning
in errore, cosa che il solo assert sul formato non avrebbe intercettato.
"""

import re
import warnings

import pytest

from app.repository.memory import MemoryUserRepository
from app.service import UserService


def _valid_data():
    return {"first_name": "Ada", "last_name": "Lovelace", "email": "ada@b.com"}


@pytest.mark.req("REQ-USR-F01")
def test_now_does_not_use_deprecated_utcnow():
    """BUG-01: la generazione dei timestamp non deve emettere DeprecationWarning."""
    svc = UserService(MemoryUserRepository())

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        user = svc.create_user(_valid_data())

    assert user["created_at"] == user["updated_at"]


@pytest.mark.req("REQ-USR-F01")
def test_timestamp_format_is_iso8601_utc():
    """Il formato resta `YYYY-MM-DDTHH:MM:SSZ` dopo il fix."""
    svc = UserService(MemoryUserRepository())

    user = svc.create_user(_valid_data())

    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", user["created_at"])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", user["updated_at"])


@pytest.mark.req("REQ-USR-E05")
def test_update_timestamp_does_not_use_deprecated_utcnow():
    """Anche il percorso di aggiornamento deve essere privo di warning."""
    svc = UserService(MemoryUserRepository())
    created = svc.create_user(_valid_data())

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        updated = svc.update_user(created["id"], {"company": "ACME"})

    assert updated["company"] == "ACME"
