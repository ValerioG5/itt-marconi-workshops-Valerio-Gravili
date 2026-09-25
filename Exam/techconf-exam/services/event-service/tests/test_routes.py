"""T-15 — Test del layer HTTP.

Il test client Flask usa il repository in memoria; le chiamate a user-service
passano dal vero UserClient ma la rete è intercettata da `responses`. Così si
verifica anche il mapping eccezione → status code.
"""

import json

import pytest
import requests
import responses

from app import config, create_app
from app.repository.memory import MemoryEventRepository

ORGANIZER = {"id": "org1", "role": "organizer", "first_name": "A", "last_name": "B",
             "email": "a@b.c", "company": None,
             "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z"}

_CONTRACT_FIELDS = {
    "id", "title", "description", "organizer_id", "venue", "city",
    "start_date", "end_date", "capacity", "price", "status",
    "created_at", "updated_at",
}


def _payload(**kw):
    d = {"title": "PyConf Italia", "organizer_id": "org1", "venue": "Auditorium",
         "city": "Roma", "start_date": "2026-10-15", "end_date": "2026-10-16",
         "capacity": 100, "price": 149.00}
    d.update(kw)
    return d


def _user_url(user_id="org1"):
    return f"{config.USER_SERVICE_URL}/api/v1/users/{user_id}"


def _mock_organizer(role="organizer"):
    responses.add(responses.GET, _user_url(), json=dict(ORGANIZER, role=role), status=200)


@pytest.fixture
def client():
    app = create_app(repository=MemoryEventRepository())
    app.config["TESTING"] = True
    return app.test_client()


def _create(client, **kw):
    """Crea un evento assumendo che il mock dell'organizzatore sia registrato."""
    r = client.post("/api/v1/events", json=_payload(**kw))
    assert r.status_code == 201, f"Setup failed: {r.data}"
    return json.loads(r.data)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-00")
def test_health_200(client):
    r = client.get("/health")

    assert r.status_code == 200
    assert r.get_json() == {"status": "ok", "service": "event-service"}


# ---------------------------------------------------------------------------
# POST — happy path
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E01")
@responses.activate
def test_post_event_201(client):
    _mock_organizer()

    r = client.post("/api/v1/events", json=_payload())

    assert r.status_code == 201
    body = r.get_json()
    assert set(body.keys()) == _CONTRACT_FIELDS
    assert body["status"] == "draft"
    assert body["description"] is None
    assert r.headers["Location"] == f"/api/v1/events/{body['id']}"


# ---------------------------------------------------------------------------
# POST — validazione dei campi (REQ-EVT-F02)
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_missing_title(client):
    _mock_organizer()
    payload = _payload()
    del payload["title"]

    r = client.post("/api/v1/events", json=payload)

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_title_too_short(client):
    _mock_organizer()

    r = client.post("/api/v1/events", json=_payload(title="ab"))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_bad_capacity_zero(client):
    _mock_organizer()

    r = client.post("/api/v1/events", json=_payload(capacity=0))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_bad_capacity_too_large(client):
    _mock_organizer()

    r = client.post("/api/v1/events", json=_payload(capacity=10001))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_negative_price(client):
    _mock_organizer()

    r = client.post("/api/v1/events", json=_payload(price=-1))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_bad_date_format(client):
    _mock_organizer()

    r = client.post("/api/v1/events", json=_payload(start_date="15/10/2026"))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_invalid_status(client):
    _mock_organizer()

    r = client.post("/api/v1/events", json=_payload(status="archived"))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_city_too_long(client):
    _mock_organizer()

    r = client.post("/api/v1/events", json=_payload(city="x" * 61))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
def test_post_event_400_malformed_json(client):
    r = client.post("/api/v1/events", data="{not json",
                    content_type="application/json")

    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "MALFORMED_JSON"


# ---------------------------------------------------------------------------
# POST — regole di business
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-B03")
@responses.activate
def test_post_event_422_end_before_start(client):
    _mock_organizer()

    r = client.post("/api/v1/events",
                    json=_payload(start_date="2026-10-20", end_date="2026-10-15"))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-B01")
@responses.activate
def test_post_event_422_reference_not_found(client):
    responses.add(responses.GET, _user_url(), status=404,
                  json={"error": {"code": "NOT_FOUND", "message": "nope"}})

    r = client.post("/api/v1/events", json=_payload())

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "REFERENCE_NOT_FOUND"


@pytest.mark.req("REQ-EVT-B02")
@responses.activate
def test_post_event_422_invalid_organizer(client):
    _mock_organizer(role="attendee")

    r = client.post("/api/v1/events", json=_payload())

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "INVALID_ORGANIZER"


@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_post_event_503_connection_error(client):
    responses.add(responses.GET, _user_url(), body=requests.ConnectionError("refused"))

    r = client.post("/api/v1/events", json=_payload())

    assert r.status_code == 503
    assert r.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_post_event_503_on_5xx(client):
    responses.add(responses.GET, _user_url(), status=500)

    r = client.post("/api/v1/events", json=_payload())

    assert r.status_code == 503
    assert r.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


@pytest.mark.req("REQ-EVT-E01")
@responses.activate
def test_validation_precedes_dependency_call(client):
    """Nessun mock registrato: se il codice chiamasse user-service otterrebbe
    un errore di connessione (503). Deve invece fermarsi a 422."""
    r = client.post("/api/v1/events", json=_payload(title="ab"))

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"
    assert len(responses.calls) == 0


# ---------------------------------------------------------------------------
# GET singolo evento
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E03")
@responses.activate
def test_get_event_200(client):
    _mock_organizer()
    created = _create(client)

    r = client.get(f"/api/v1/events/{created['id']}")

    assert r.status_code == 200
    assert r.get_json()["id"] == created["id"]


@pytest.mark.req("REQ-EVT-E03")
def test_get_event_404(client):
    r = client.get("/api/v1/events/nonexistent-id-12345")

    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# GET lista
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E02")
@responses.activate
def test_list_events_200(client):
    _mock_organizer()
    _create(client)
    _create(client, title="Altro evento")

    r = client.get("/api/v1/events")

    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["page_size"] == 20
    assert len(body["items"]) == 2


@pytest.mark.req("REQ-EVT-B06")
@responses.activate
def test_list_events_filter_status_and_city(client):
    _mock_organizer()
    _create(client, city="Roma", status="published")
    _create(client, city="Milano", status="published")
    _create(client, city="Roma", status="draft")

    r = client.get("/api/v1/events?status=published&city=Roma")

    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 1
    assert body["items"][0]["city"] == "Roma"
    assert body["items"][0]["status"] == "published"


@pytest.mark.req("REQ-EVT-E02")
def test_list_events_422_bad_page_size(client):
    r = client.get("/api/v1/events?page_size=101")

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-B06")
def test_list_events_422_bad_status(client):
    r = client.get("/api/v1/events?status=archived")

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-E02")
def test_list_events_422_page_zero(client):
    r = client.get("/api/v1/events?page=0")

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# PUT
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E04")
@responses.activate
def test_put_event_200(client):
    _mock_organizer()
    created = _create(client)

    r = client.put(f"/api/v1/events/{created['id']}",
                   json=_payload(title="Titolo sostituito", city="Milano"))

    assert r.status_code == 200
    body = r.get_json()
    assert body["title"] == "Titolo sostituito"
    assert body["city"] == "Milano"
    assert body["id"] == created["id"]
    assert body["created_at"] == created["created_at"]


@pytest.mark.req("REQ-EVT-E04")
@responses.activate
def test_put_event_404(client):
    _mock_organizer()

    r = client.put("/api/v1/events/nonexistent-id", json=_payload())

    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# PATCH
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E05")
@responses.activate
def test_patch_event_200(client):
    _mock_organizer()
    created = _create(client)

    r = client.patch(f"/api/v1/events/{created['id']}", json={"capacity": 250})

    assert r.status_code == 200
    body = r.get_json()
    assert body["capacity"] == 250
    assert body["title"] == created["title"]


@pytest.mark.req("REQ-EVT-B04")
@responses.activate
def test_patch_status_published_then_draft_422(client):
    _mock_organizer()
    created = _create(client)

    r1 = client.patch(f"/api/v1/events/{created['id']}", json={"status": "published"})
    assert r1.status_code == 200

    r2 = client.patch(f"/api/v1/events/{created['id']}", json={"status": "draft"})

    assert r2.status_code == 422
    assert r2.get_json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-E06")
@responses.activate
def test_delete_event_204_then_404(client):
    _mock_organizer()
    created = _create(client)

    r = client.delete(f"/api/v1/events/{created['id']}")
    assert r.status_code == 204
    assert r.data == b""

    assert client.get(f"/api/v1/events/{created['id']}").status_code == 404


@pytest.mark.req("REQ-EVT-E06")
def test_delete_event_404(client):
    r = client.delete("/api/v1/events/nonexistent-id")

    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "NOT_FOUND"


# -----------------------------------------------------------------------
# BUG-02 — campi stringa whitespace-only
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_whitespace_title(client):
    """BUG-02: criterio 16."""
    _mock_organizer()
    r = client.post("/api/v1/events", json=_payload(title="     "))
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_whitespace_venue(client):
    """BUG-02: criterio 17."""
    _mock_organizer()
    r = client.post("/api/v1/events", json=_payload(venue="   "))
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_422_whitespace_city(client):
    """BUG-02: criterio 18."""
    _mock_organizer()
    r = client.post("/api/v1/events", json=_payload(city="  "))
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-EVT-F02")
@responses.activate
def test_post_event_201_preserves_inner_spaces(client):
    """Il .strip() decide solo se accettare: non riscrive il valore."""
    _mock_organizer()
    r = client.post("/api/v1/events", json=_payload(title="PyConf Italia 2026"))
    assert r.status_code == 201
    assert r.get_json()["title"] == "PyConf Italia 2026"
