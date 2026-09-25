"""T-14 — Test unitari della business logic.

Nessun Flask, nessuna rete: il repository è quello in memoria e user-service è
sostituito da un fake iniettato. Questo isola le regole di dominio
(organizzatore, date, transizioni) dal layer HTTP.
"""

import uuid

import pytest

from app.repository.base import (
    DependencyUnavailableError,
    EventNotFoundError,
    InvalidOrganizerError,
    InvalidStatusTransitionError,
    ValidationError,
)
from app.repository.memory import MemoryEventRepository
from app.service import EventService

ORGANIZER = {"id": "org1", "role": "organizer", "first_name": "A", "last_name": "B",
             "email": "a@b.c", "company": None,
             "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z"}

ATTENDEE = dict(ORGANIZER, role="attendee")


def _payload(**kw):
    d = {"title": "PyConf Italia", "organizer_id": "org1", "venue": "Auditorium",
         "city": "Roma", "start_date": "2026-10-15", "end_date": "2026-10-16",
         "capacity": 100, "price": 149.00}
    d.update(kw)
    return d


class FakeUserClient:
    """Fake iniettabile: registra le chiamate per verificare che PATCH senza
    organizer_id non tocchi user-service (REQ-EVT-B01 criterio 5)."""

    def __init__(self, user=None, exc=None):
        self.user, self.exc, self.calls = user, exc, 0

    def get_user(self, user_id):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.user


def _service(user=ORGANIZER, exc=None):
    """Costruisce un EventService con repo in memoria e fake client."""
    uc = FakeUserClient(user=user, exc=exc)
    return EventService(MemoryEventRepository(), uc), uc


# ---------------------------------------------------------------------------
# Creazione
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-F01", "REQ-EVT-E01")
def test_create_event_ok():
    svc, uc = _service()

    event = svc.create_event(_payload())

    # id generato server-side come UUID v4
    assert uuid.UUID(event["id"]).version == 4
    assert event["status"] == "draft"
    # criterio 3: created_at e updated_at coincidono alla creazione
    assert event["created_at"] == event["updated_at"]
    assert event["created_at"].endswith("Z")
    assert uc.calls == 1


@pytest.mark.req("REQ-EVT-F02")
def test_create_event_defaults_description_none():
    svc, _ = _service()

    event = svc.create_event(_payload())

    assert event["description"] is None


@pytest.mark.req("REQ-EVT-B01")
def test_create_event_organizer_not_found():
    from app.repository.base import OrganizerNotFoundError

    svc, _ = _service(exc=OrganizerNotFoundError("org1"))

    with pytest.raises(OrganizerNotFoundError):
        svc.create_event(_payload())


@pytest.mark.req("REQ-EVT-B02")
def test_create_event_invalid_organizer_role():
    svc, _ = _service(user=ATTENDEE)

    with pytest.raises(InvalidOrganizerError):
        svc.create_event(_payload())


@pytest.mark.req("REQ-EVT-B05")
def test_create_event_dependency_unavailable():
    svc, _ = _service(exc=DependencyUnavailableError("down"))

    with pytest.raises(DependencyUnavailableError):
        svc.create_event(_payload())


@pytest.mark.req("REQ-EVT-B03")
def test_create_event_end_before_start():
    svc, uc = _service()

    with pytest.raises(ValidationError):
        svc.create_event(_payload(start_date="2026-10-20", end_date="2026-10-15"))

    # le date sono validate prima della dipendenza
    assert uc.calls == 0


@pytest.mark.req("REQ-EVT-B03")
def test_create_event_same_day_ok():
    svc, _ = _service()

    event = svc.create_event(_payload(start_date="2026-10-15", end_date="2026-10-15"))

    assert event["start_date"] == event["end_date"]


# ---------------------------------------------------------------------------
# Transizioni di stato (REQ-EVT-B04)
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-B04")
def test_transition_draft_to_published():
    svc, _ = _service()
    created = svc.create_event(_payload())

    updated = svc.update_event(created["id"], {"status": "published"})

    assert updated["status"] == "published"


@pytest.mark.req("REQ-EVT-B04")
def test_transition_draft_to_cancelled():
    svc, _ = _service()
    created = svc.create_event(_payload())

    updated = svc.update_event(created["id"], {"status": "cancelled"})

    assert updated["status"] == "cancelled"


@pytest.mark.req("REQ-EVT-B04")
def test_transition_published_to_cancelled():
    svc, _ = _service()
    created = svc.create_event(_payload(status="published"))

    updated = svc.update_event(created["id"], {"status": "cancelled"})

    assert updated["status"] == "cancelled"


@pytest.mark.req("REQ-EVT-B04")
def test_transition_published_to_draft_rejected():
    svc, _ = _service()
    created = svc.create_event(_payload(status="published"))

    with pytest.raises(InvalidStatusTransitionError):
        svc.update_event(created["id"], {"status": "draft"})


@pytest.mark.req("REQ-EVT-B04")
def test_transition_from_cancelled_rejected():
    """cancelled è terminale: nessuna transizione in uscita."""
    svc, _ = _service()
    created = svc.create_event(_payload(status="cancelled"))

    with pytest.raises(InvalidStatusTransitionError):
        svc.update_event(created["id"], {"status": "published"})
    with pytest.raises(InvalidStatusTransitionError):
        svc.update_event(created["id"], {"status": "draft"})


@pytest.mark.req("REQ-EVT-B04")
def test_transition_same_status_is_noop():
    svc, _ = _service()
    created = svc.create_event(_payload(status="cancelled"))

    updated = svc.update_event(created["id"], {"status": "cancelled"})

    assert updated["status"] == "cancelled"


# ---------------------------------------------------------------------------
# PATCH: validazione delle date sul merge (REQ-EVT-B03 criteri 3-5)
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-B03")
def test_patch_only_start_date_validates_against_stored_end():
    svc, _ = _service()
    created = svc.create_event(_payload(start_date="2026-10-15", end_date="2026-10-16"))

    with pytest.raises(ValidationError):
        svc.update_event(created["id"], {"start_date": "2026-11-01"})


@pytest.mark.req("REQ-EVT-B03")
def test_patch_only_end_date_validates_against_stored_start():
    svc, _ = _service()
    created = svc.create_event(_payload(start_date="2026-10-15", end_date="2026-10-16"))

    with pytest.raises(ValidationError):
        svc.update_event(created["id"], {"end_date": "2026-09-01"})


@pytest.mark.req("REQ-EVT-B01")
def test_patch_without_organizer_id_does_not_call_user_service():
    svc, uc = _service()
    created = svc.create_event(_payload())
    calls_after_create = uc.calls

    svc.update_event(created["id"], {"title": "Nuovo titolo"})

    assert uc.calls == calls_after_create


# ---------------------------------------------------------------------------
# PUT (REQ-EVT-E04)
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E04")
def test_replace_preserves_id_and_created_at():
    svc, _ = _service()
    created = svc.create_event(_payload())

    replaced = svc.replace_event(created["id"], _payload(title="Titolo sostituito"))

    assert replaced["id"] == created["id"]
    assert replaced["created_at"] == created["created_at"]
    assert replaced["title"] == "Titolo sostituito"


@pytest.mark.req("REQ-EVT-E04")
def test_replace_without_status_preserves_stored_status():
    svc, _ = _service()
    created = svc.create_event(_payload())
    svc.update_event(created["id"], {"status": "published"})

    replaced = svc.replace_event(created["id"], _payload(city="Milano"))

    assert replaced["status"] == "published"
    assert replaced["city"] == "Milano"


# ---------------------------------------------------------------------------
# Lettura, lista, cancellazione
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E02")
def test_list_events_pagination():
    svc, _ = _service()
    for i in range(5):
        svc.create_event(_payload(title=f"Evento {i}"))

    page1, total = svc.list_events(None, None, page=1, page_size=2)
    page3, total3 = svc.list_events(None, None, page=3, page_size=2)

    assert total == 5 and total3 == 5
    assert len(page1) == 2
    assert len(page3) == 1


@pytest.mark.req("REQ-EVT-E06")
def test_delete_event_then_get_raises():
    svc, _ = _service()
    created = svc.create_event(_payload())

    svc.delete_event(created["id"])

    with pytest.raises(EventNotFoundError):
        svc.get_event(created["id"])


@pytest.mark.req("REQ-EVT-E03")
def test_get_event_not_found():
    svc, _ = _service()

    with pytest.raises(EventNotFoundError):
        svc.get_event("missing")
