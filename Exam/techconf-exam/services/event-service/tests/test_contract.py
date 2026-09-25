"""T-16 — Test di contratto contro contracts/openapi/event-service.yaml.

Almeno un test per endpoint, più i formati di errore. Il validator è parte del
template non modificabile, quindi è il test ad adattarsi alla sua interfaccia.
"""

import json
import os
import sys

import pytest
import requests
import responses

# Aggiungi la workspace root (techconf-exam/) a sys.path per importare contracts.validator
# tests/ -> .. -> event-service/ -> .. -> services/ -> .. -> techconf-exam/
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _WORKSPACE_ROOT)

from contracts.validator import assert_matches_contract
from app import config, create_app
from app.repository.memory import MemoryEventRepository

ORGANIZER = {"id": "org1", "role": "organizer", "first_name": "A", "last_name": "B",
             "email": "a@b.c", "company": None,
             "created_at": "2025-01-01T00:00:00Z", "updated_at": "2025-01-01T00:00:00Z"}


def _payload(**kw):
    d = {"title": "PyConf Italia", "organizer_id": "org1", "venue": "Auditorium",
         "city": "Roma", "start_date": "2026-10-15", "end_date": "2026-10-16",
         "capacity": 100, "price": 149.00}
    d.update(kw)
    return d


@pytest.fixture
def client():
    app = create_app(repository=MemoryEventRepository())
    app.config["TESTING"] = True
    return app.test_client()


def _adapt(response):
    """Adatta una Flask test response al formato dict atteso dal validator.

    Il validator (contracts/validator.py, non modificabile) si aspetta un
    oggetto stile ``requests.Response`` con ``json()`` chiamabile, oppure un
    dict ``{"status_code", "headers", "json"}``. La Flask test response espone
    ``json`` come proprietà (non chiamabile), quindi la convertiamo qui.
    """
    body = None
    if response.data and response.data.strip():
        body = json.loads(response.data)
    return {
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "json": body,
    }


def _user_url(user_id="org1"):
    return f"{config.USER_SERVICE_URL}/api/v1/users/{user_id}"


def _mock_organizer(role="organizer"):
    responses.add(responses.GET, _user_url(), json=dict(ORGANIZER, role=role), status=200)


def _post_event(client, **kw):
    r = client.post("/api/v1/events", json=_payload(**kw))
    assert r.status_code == 201, f"Setup failed: {r.data}"
    return json.loads(r.data)


# -----------------------------------------------------------------------
# Ogni test chiama assert_matches_contract per verificare la risposta
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-C01")
def test_contract_health(client):
    r = client.get("/health")
    assert_matches_contract("event-service", "GET", "/health", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
@responses.activate
def test_contract_post_event(client):
    _mock_organizer()
    r = client.post("/api/v1/events", json=_payload())
    assert r.status_code == 201
    assert_matches_contract("event-service", "POST", "/api/v1/events", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
@responses.activate
def test_contract_get_event(client):
    _mock_organizer()
    created = _post_event(client)
    r = client.get(f"/api/v1/events/{created['id']}")
    assert_matches_contract("event-service", "GET", f"/api/v1/events/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
@responses.activate
def test_contract_list_events(client):
    _mock_organizer()
    _post_event(client)
    r = client.get("/api/v1/events")
    assert_matches_contract("event-service", "GET", "/api/v1/events", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
@responses.activate
def test_contract_put_event(client):
    _mock_organizer()
    created = _post_event(client)
    r = client.put(f"/api/v1/events/{created['id']}", json=_payload(title="Sostituito"))
    assert_matches_contract("event-service", "PUT", f"/api/v1/events/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
@responses.activate
def test_contract_patch_event(client):
    _mock_organizer()
    created = _post_event(client)
    r = client.patch(f"/api/v1/events/{created['id']}", json={"status": "published"})
    assert_matches_contract("event-service", "PATCH", f"/api/v1/events/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
@responses.activate
def test_contract_delete_event(client):
    _mock_organizer()
    created = _post_event(client)
    r = client.delete(f"/api/v1/events/{created['id']}")
    assert_matches_contract("event-service", "DELETE", f"/api/v1/events/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
def test_contract_error_404(client):
    r = client.get("/api/v1/events/nonexistent-id-12345")
    assert r.status_code == 404
    assert_matches_contract("event-service", "GET", "/api/v1/events/nonexistent-id-12345", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
@responses.activate
def test_contract_error_422_reference_not_found(client):
    responses.add(responses.GET, _user_url(), status=404,
                  json={"error": {"code": "NOT_FOUND", "message": "nope"}})
    r = client.post("/api/v1/events", json=_payload())
    assert r.status_code == 422
    assert_matches_contract("event-service", "POST", "/api/v1/events", _adapt(r))


@pytest.mark.req("REQ-EVT-C01")
@responses.activate
def test_contract_error_503(client):
    responses.add(responses.GET, _user_url(), body=requests.ConnectionError("refused"))
    r = client.post("/api/v1/events", json=_payload())
    assert r.status_code == 503
    assert_matches_contract("event-service", "POST", "/api/v1/events", _adapt(r))
