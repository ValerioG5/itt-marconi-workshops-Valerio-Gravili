"""T-14 — Test unitari della business logic.

Repository reale in memoria (le regole di capienza dipendono dal suo
comportamento, non va simulato) e client finti che contano le invocazioni:
così `test_patch_does_not_call_dependencies` può verificare l'assenza di I/O.
"""

import uuid

import pytest

from app.repository.base import (
    AlreadyRegisteredError,
    DependencyUnavailableError,
    EventFullError,
    EventNotFoundForStatsError,
    EventNotOpenError,
    InvalidStatusTransitionError,
    ReferenceNotFoundError,
    RegistrationNotFoundError,
)
from app.repository.memory import MemoryRegistrationRepository
from app.service import RegistrationService


class FakeUserClient:
    def __init__(self, exc=None):
        self.exc, self.calls = exc, 0

    def get_user(self, user_id):
        self.calls += 1
        if self.exc:
            raise self.exc
        return {"id": user_id, "role": "attendee"}


class FakeEventClient:
    def __init__(self, event=None, exc=None):
        self.event, self.exc, self.calls = event, exc, 0

    def get_event(self, event_id):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.event


def _event(capacity=10, price=149.0, status="published"):
    return {"id": "e1", "capacity": capacity, "price": price, "status": status}


def _service(event=None, user_exc=None, event_exc=None, repository=None):
    """Restituisce (service, repo, user_client, event_client)."""
    repo = repository if repository is not None else MemoryRegistrationRepository()
    uc = FakeUserClient(user_exc)
    ec = FakeEventClient(event if event is not None else _event(), event_exc)
    return RegistrationService(repo, uc, ec), repo, uc, ec


def _data(user="u1", event="e1", **kw):
    d = {"user_id": user, "event_id": event}
    d.update(kw)
    return d


# -----------------------------------------------------------------------
# Creazione
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-E01")
def test_create_registration_ok():
    service, _, _, _ = _service()

    reg = service.create_registration(_data())

    assert reg["status"] == "confirmed"
    assert uuid.UUID(reg["id"]).version == 4
    assert reg["created_at"] == reg["updated_at"]
    assert reg["user_id"] == "u1"
    assert reg["event_id"] == "e1"


@pytest.mark.req("REQ-REG-B06")
def test_amount_copied_from_event_price():
    service, _, _, _ = _service(event=_event(price=199.99))

    assert service.create_registration(_data())["amount"] == 199.99


@pytest.mark.req("REQ-REG-B06")
def test_amount_in_payload_is_ignored():
    """`amount` è read-only: quello che arriva dal client non viene guardato."""
    service, _, _, _ = _service(event=_event(price=149.0))

    reg = service.create_registration(_data(amount=0, status="cancelled"))

    assert reg["amount"] == 149.0
    assert reg["status"] == "confirmed"


@pytest.mark.req("REQ-REG-B06")
def test_amount_zero_price():
    service, _, _, _ = _service(event=_event(price=0))

    assert service.create_registration(_data())["amount"] == 0


@pytest.mark.req("REQ-REG-B01")
def test_user_not_found():
    service, _, _, ec = _service(user_exc=ReferenceNotFoundError("u1"))

    with pytest.raises(ReferenceNotFoundError):
        service.create_registration(_data())

    assert ec.calls == 0   # l'evento non viene nemmeno interrogato


@pytest.mark.req("REQ-REG-B02")
def test_event_not_found():
    service, _, _, _ = _service(event_exc=ReferenceNotFoundError("e1"))

    with pytest.raises(ReferenceNotFoundError):
        service.create_registration(_data())


@pytest.mark.req("REQ-REG-B09")
def test_dependency_unavailable_propagates():
    service, _, _, _ = _service(event_exc=DependencyUnavailableError("down"))

    with pytest.raises(DependencyUnavailableError):
        service.create_registration(_data())


@pytest.mark.req("REQ-REG-B03")
def test_event_draft_rejected():
    service, _, _, _ = _service(event=_event(status="draft"))

    with pytest.raises(EventNotOpenError):
        service.create_registration(_data())


@pytest.mark.req("REQ-REG-B03")
def test_event_cancelled_rejected():
    service, _, _, _ = _service(event=_event(status="cancelled"))

    with pytest.raises(EventNotOpenError):
        service.create_registration(_data())


# -----------------------------------------------------------------------
# Doppia iscrizione
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B04")
def test_double_confirmed_registration_rejected():
    service, _, _, _ = _service()
    service.create_registration(_data())

    with pytest.raises(AlreadyRegisteredError):
        service.create_registration(_data())


@pytest.mark.req("REQ-REG-B04")
def test_registration_allowed_after_cancellation():
    service, repo, _, _ = _service()
    first = service.create_registration(_data())
    service.update_status(first["id"], "cancelled")

    second = service.create_registration(_data())

    assert second["status"] == "confirmed"
    assert second["id"] != first["id"]
    assert repo.count_confirmed("e1") == 1


@pytest.mark.req("REQ-REG-B04")
def test_different_user_same_event_allowed():
    service, repo, _, _ = _service()
    service.create_registration(_data(user="u1"))

    service.create_registration(_data(user="u2"))

    assert repo.count_confirmed("e1") == 2


@pytest.mark.req("REQ-REG-B04")
def test_same_user_different_event_allowed():
    service, repo, _, _ = _service()
    service.create_registration(_data(event="e1"))

    service.create_registration(_data(event="e2"))

    assert repo.count_confirmed("e1") == 1
    assert repo.count_confirmed("e2") == 1


# -----------------------------------------------------------------------
# Capienza
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B05")
def test_capacity_reached_rejected():
    service, _, _, _ = _service(event=_event(capacity=2))
    service.create_registration(_data(user="u1"))
    service.create_registration(_data(user="u2"))

    with pytest.raises(EventFullError):
        service.create_registration(_data(user="u3"))


@pytest.mark.req("REQ-REG-B05")
def test_capacity_one_second_rejected():
    service, _, _, _ = _service(event=_event(capacity=1))
    service.create_registration(_data(user="u1"))

    with pytest.raises(EventFullError):
        service.create_registration(_data(user="u2"))


@pytest.mark.req("REQ-REG-B05", "REQ-REG-B07")
def test_cancel_frees_seat():
    service, _, _, _ = _service(event=_event(capacity=1))
    first = service.create_registration(_data(user="u1"))
    service.update_status(first["id"], "cancelled")

    second = service.create_registration(_data(user="u2"))

    assert second["status"] == "confirmed"


@pytest.mark.req("REQ-REG-B05")
def test_cancelled_not_counted_in_capacity():
    service, repo, _, _ = _service(event=_event(capacity=3))
    a = service.create_registration(_data(user="u1"))
    service.create_registration(_data(user="u2"))
    service.update_status(a["id"], "cancelled")

    assert repo.count_confirmed("e1") == 1
    assert len(repo.list_all(None, "e1", None)) == 2


# -----------------------------------------------------------------------
# Transizioni di stato
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B07")
def test_transition_confirmed_to_cancelled():
    service, _, _, _ = _service()
    reg = service.create_registration(_data())

    updated = service.update_status(reg["id"], "cancelled")

    assert updated["status"] == "cancelled"


@pytest.mark.req("REQ-REG-B07")
def test_transition_cancelled_to_confirmed_rejected():
    service, _, _, _ = _service()
    reg = service.create_registration(_data())
    service.update_status(reg["id"], "cancelled")

    with pytest.raises(InvalidStatusTransitionError):
        service.update_status(reg["id"], "confirmed")


@pytest.mark.req("REQ-REG-B07")
def test_transition_same_status_noop():
    service, _, _, _ = _service()
    reg = service.create_registration(_data())

    updated = service.update_status(reg["id"], "confirmed")

    assert updated["status"] == "confirmed"


@pytest.mark.req("REQ-REG-B07")
def test_patch_does_not_call_dependencies():
    service, _, uc, ec = _service()
    reg = service.create_registration(_data())
    user_calls, event_calls = uc.calls, ec.calls

    service.update_status(reg["id"], "cancelled")

    assert uc.calls == user_calls
    assert ec.calls == event_calls


@pytest.mark.req("REQ-REG-E04")
def test_update_status_not_found():
    service, _, _, _ = _service()

    with pytest.raises(RegistrationNotFoundError):
        service.update_status("missing", "cancelled")


# -----------------------------------------------------------------------
# Stats
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B08")
def test_stats_ok():
    service, _, _, _ = _service(event=_event(capacity=5))
    service.create_registration(_data(user="u1"))
    service.create_registration(_data(user="u2"))

    stats = service.get_stats("e1")

    assert stats == {"event_id": "e1", "capacity": 5, "confirmed": 2, "available": 3}


@pytest.mark.req("REQ-REG-B08")
def test_stats_available_clamped_at_zero():
    """Se la capienza dell'evento viene ridotta a posteriori, `available` non
    deve diventare negativo."""
    service, _, _, ec = _service(event=_event(capacity=2))
    service.create_registration(_data(user="u1"))
    service.create_registration(_data(user="u2"))
    ec.event["capacity"] = 1

    stats = service.get_stats("e1")

    assert stats["confirmed"] == 2
    assert stats["available"] == 0


@pytest.mark.req("REQ-REG-B08")
def test_stats_event_not_found():
    """Il 404 remoto diventa EventNotFoundForStatsError, non ReferenceNotFoundError:
    la route deve poter rispondere 404 e non 422."""
    service, _, _, _ = _service(event_exc=ReferenceNotFoundError("e1"))

    with pytest.raises(EventNotFoundForStatsError):
        service.get_stats("e1")


# -----------------------------------------------------------------------
# Lettura, lista, cancellazione
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-E03")
def test_get_registration_ok_and_not_found():
    service, _, _, _ = _service()
    reg = service.create_registration(_data())

    assert service.get_registration(reg["id"])["id"] == reg["id"]
    with pytest.raises(RegistrationNotFoundError):
        service.get_registration("missing")


@pytest.mark.req("REQ-REG-E02")
def test_list_registrations_filters_and_pagination():
    service, _, _, _ = _service(event=_event(capacity=50))
    for i in range(3):
        service.create_registration(_data(user=f"u{i}", event="e1"))
    service.create_registration(_data(user="u0", event="e2"))

    items, total = service.list_registrations(None, "e1", None, 1, 2)
    assert total == 3
    assert len(items) == 2

    items, total = service.list_registrations(None, "e1", None, 2, 2)
    assert total == 3
    assert len(items) == 1

    items, total = service.list_registrations("u0", None, None, 1, 20)
    assert total == 2

    items, total = service.list_registrations(None, None, "cancelled", 1, 20)
    assert total == 0


@pytest.mark.req("REQ-REG-E05")
def test_delete_frees_seat():
    service, repo, _, _ = _service(event=_event(capacity=1))
    first = service.create_registration(_data(user="u1"))

    service.delete_registration(first["id"])

    assert repo.count_confirmed("e1") == 0
    assert service.create_registration(_data(user="u2"))["status"] == "confirmed"
