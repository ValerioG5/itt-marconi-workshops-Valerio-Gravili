"""T-16 — Test di contratto contro contracts/openapi/registration-service.yaml.

Almeno un test per endpoint, più i formati di errore (404, 422, 409, 503, 405).
Il validator è parte del template non modificabile, quindi è il test ad
adattarsi alla sua interfaccia.
"""

import json
import os
import sys

import pytest
import requests
import responses

# Aggiungi la workspace root (techconf-exam/) a sys.path per importare contracts.validator
# tests/ -> .. -> registration-service/ -> .. -> services/ -> .. -> techconf-exam/
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _WORKSPACE_ROOT)

from contracts.validator import assert_matches_contract
from app import config, create_app
from app.repository.memory import MemoryRegistrationRepository

USER_ID = "11111111-1111-4111-8111-111111111111"
OTHER_USER_ID = "33333333-3333-4333-8333-333333333333"
EVENT_ID = "22222222-2222-4222-8222-222222222222"


@pytest.fixture
def client():
    app = create_app(repository=MemoryRegistrationRepository())
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


def _user_url(user_id=USER_ID):
    return f"{config.USER_SERVICE_URL}/api/v1/users/{user_id}"


def _event_url(event_id=EVENT_ID):
    return f"{config.EVENT_SERVICE_URL}/api/v1/events/{event_id}"


def _mock_user(user_id=USER_ID):
    responses.add(responses.GET, _user_url(user_id), status=200,
                  json={"id": user_id, "role": "attendee"})


def _mock_event(capacity=10, price=149.0, status="published"):
    responses.add(responses.GET, _event_url(), status=200,
                  json={"id": EVENT_ID, "capacity": capacity, "price": price,
                        "status": status})


def _post_registration(client, user_id=USER_ID):
    r = client.post("/api/v1/registrations",
                    json={"user_id": user_id, "event_id": EVENT_ID})
    assert r.status_code == 201, f"Setup failed: {r.data}"
    return json.loads(r.data)


# -----------------------------------------------------------------------
# Ogni test chiama assert_matches_contract per verificare la risposta
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-C01")
def test_contract_health(client):
    r = client.get("/health")
    assert_matches_contract("registration-service", "GET", "/health", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
@responses.activate
def test_contract_post_registration(client):
    _mock_user()
    _mock_event()
    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})
    assert r.status_code == 201, r.data
    assert_matches_contract("registration-service", "POST", "/api/v1/registrations", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
@responses.activate
def test_contract_list_registrations(client):
    _mock_user()
    _mock_event()
    _post_registration(client)
    r = client.get("/api/v1/registrations")
    assert r.status_code == 200
    assert_matches_contract("registration-service", "GET", "/api/v1/registrations", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
@responses.activate
def test_contract_stats(client):
    _mock_user()
    _mock_event(capacity=5)
    _post_registration(client)
    r = client.get(f"/api/v1/registrations/stats?event_id={EVENT_ID}")
    assert r.status_code == 200, r.data
    assert_matches_contract("registration-service", "GET",
                            "/api/v1/registrations/stats", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
@responses.activate
def test_contract_get_registration(client):
    _mock_user()
    _mock_event()
    created = _post_registration(client)
    r = client.get(f"/api/v1/registrations/{created['id']}")
    assert_matches_contract("registration-service", "GET",
                            f"/api/v1/registrations/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
@responses.activate
def test_contract_patch_registration(client):
    _mock_user()
    _mock_event()
    created = _post_registration(client)
    r = client.patch(f"/api/v1/registrations/{created['id']}",
                     json={"status": "cancelled"})
    assert r.status_code == 200, r.data
    assert_matches_contract("registration-service", "PATCH",
                            f"/api/v1/registrations/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
@responses.activate
def test_contract_delete_registration(client):
    _mock_user()
    _mock_event()
    created = _post_registration(client)
    r = client.delete(f"/api/v1/registrations/{created['id']}")
    assert r.status_code == 204
    assert_matches_contract("registration-service", "DELETE",
                            f"/api/v1/registrations/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-REG-C01", "REQ-REG-E06")
def test_contract_put_405(client):
    r = client.put(f"/api/v1/registrations/{EVENT_ID}", json={"status": "cancelled"})
    assert r.status_code == 405
    assert_matches_contract("registration-service", "PUT",
                            f"/api/v1/registrations/{EVENT_ID}", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
def test_contract_error_404(client):
    r = client.get("/api/v1/registrations/nonexistent-id-12345")
    assert r.status_code == 404
    assert_matches_contract("registration-service", "GET",
                            "/api/v1/registrations/nonexistent-id-12345", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
def test_contract_error_422(client):
    r = client.post("/api/v1/registrations", json={"event_id": EVENT_ID})
    assert r.status_code == 422
    assert_matches_contract("registration-service", "POST", "/api/v1/registrations", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
@responses.activate
def test_contract_error_409(client):
    _mock_user()
    _mock_event()
    _post_registration(client)
    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})
    assert r.status_code == 409, r.data
    assert_matches_contract("registration-service", "POST", "/api/v1/registrations", _adapt(r))


@pytest.mark.req("REQ-REG-C01")
@responses.activate
def test_contract_error_503(client):
    responses.add(responses.GET, _user_url(), body=requests.ConnectionError("refused"))
    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})
    assert r.status_code == 503, r.data
    assert_matches_contract("registration-service", "POST", "/api/v1/registrations", _adapt(r))
