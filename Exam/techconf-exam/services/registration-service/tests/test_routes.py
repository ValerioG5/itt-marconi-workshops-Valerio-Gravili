"""T-15 — Test del layer HTTP con il test client Flask.

Le dipendenze remote sono intercettate con `responses`; gli URL sono derivati
da `app.config` così restano allineati a quelli che i client costruiscono
davvero. Il repository è quello reale in memoria.
"""

import json

import pytest
import requests
import responses

from app import config, create_app
from app.repository.memory import MemoryRegistrationRepository

USER_ID = "11111111-1111-4111-8111-111111111111"
EVENT_ID = "22222222-2222-4222-8222-222222222222"

REGISTRATION_KEYS = {
    "id", "user_id", "event_id", "amount", "status", "created_at", "updated_at",
}


@pytest.fixture
def client():
    app = create_app(repository=MemoryRegistrationRepository())
    app.config["TESTING"] = True
    return app.test_client()


def _user_url(user_id=USER_ID):
    return f"{config.USER_SERVICE_URL}/api/v1/users/{user_id}"


def _event_url(event_id=EVENT_ID):
    return f"{config.EVENT_SERVICE_URL}/api/v1/events/{event_id}"


def _mock_user(user_id=USER_ID, status=200):
    body = {"id": user_id, "role": "attendee", "first_name": "A", "last_name": "B",
            "email": "a@b.c"}
    if status == 200:
        responses.add(responses.GET, _user_url(user_id), json=body, status=200)
    else:
        responses.add(responses.GET, _user_url(user_id), status=status,
                      json={"error": {"code": "NOT_FOUND", "message": "nope"}})


def _mock_event(event_id=EVENT_ID, status=200, capacity=10, price=149.0,
                event_status="published"):
    if status == 200:
        responses.add(
            responses.GET, _event_url(event_id), status=200,
            json={"id": event_id, "capacity": capacity, "price": price,
                  "status": event_status},
        )
    else:
        responses.add(responses.GET, _event_url(event_id), status=status,
                      json={"error": {"code": "NOT_FOUND", "message": "nope"}})


def _create(client, user_id=USER_ID, event_id=EVENT_ID):
    r = client.post("/api/v1/registrations",
                    json={"user_id": user_id, "event_id": event_id})
    assert r.status_code == 201, f"Setup failed: {r.data}"
    return json.loads(r.data)


# -----------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-00")
def test_health(client):
    r = client.get("/health")

    assert r.status_code == 200
    assert r.get_json() == {"status": "ok", "service": "registration-service"}


# -----------------------------------------------------------------------
# POST
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-E01", "REQ-REG-F01")
@responses.activate
def test_post_registration_201(client):
    _mock_user()
    _mock_event(price=149.0)

    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})

    assert r.status_code == 201, r.data
    body = r.get_json()
    assert set(body) == REGISTRATION_KEYS
    assert body["status"] == "confirmed"
    assert body["amount"] == 149.0
    assert r.headers["Location"] == f"/api/v1/registrations/{body['id']}"


@pytest.mark.req("REQ-REG-F02")
def test_post_malformed_json_400(client):
    r = client.post("/api/v1/registrations", data="{not json",
                    content_type="application/json")

    assert r.status_code == 400
    assert r.get_json()["error"]["code"] == "MALFORMED_JSON"


@pytest.mark.req("REQ-REG-F02")
def test_post_missing_user_id_422(client):
    r = client.post("/api/v1/registrations", json={"event_id": EVENT_ID})

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-REG-F02")
def test_post_missing_event_id_422(client):
    r = client.post("/api/v1/registrations", json={"user_id": USER_ID})

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-REG-F02")
def test_post_blank_user_id_422(client):
    r = client.post("/api/v1/registrations",
                    json={"user_id": "  ", "event_id": EVENT_ID})

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-REG-F02")
@responses.activate
def test_validation_precedes_dependency_call(client):
    """Nessun mock registrato: se la route chiamasse le dipendenze prima di
    validare, `responses` solleverebbe ConnectionError e vedremmo un 503."""
    r = client.post("/api/v1/registrations", json={})

    assert r.status_code == 422
    assert len(responses.calls) == 0


@pytest.mark.req("REQ-REG-B01")
@responses.activate
def test_post_user_not_found_422(client):
    _mock_user(status=404)

    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})

    assert r.status_code == 422, r.data
    assert r.get_json()["error"]["code"] == "REFERENCE_NOT_FOUND"


@pytest.mark.req("REQ-REG-B02")
@responses.activate
def test_post_event_not_found_422(client):
    _mock_user()
    _mock_event(status=404)

    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})

    assert r.status_code == 422, r.data
    assert r.get_json()["error"]["code"] == "REFERENCE_NOT_FOUND"


@pytest.mark.req("REQ-REG-B03")
@responses.activate
def test_post_event_not_open_422(client):
    _mock_user()
    _mock_event(event_status="draft")

    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})

    assert r.status_code == 422, r.data
    assert r.get_json()["error"]["code"] == "EVENT_NOT_OPEN"


@pytest.mark.req("REQ-REG-B04")
@responses.activate
def test_post_already_registered_409(client):
    _mock_user()
    _mock_event()
    _create(client)

    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})

    assert r.status_code == 409, r.data
    assert r.get_json()["error"]["code"] == "ALREADY_REGISTERED"


@pytest.mark.req("REQ-REG-B05")
@responses.activate
def test_post_event_full_409(client):
    other_user = "33333333-3333-4333-8333-333333333333"
    _mock_user()
    _mock_user(other_user)
    _mock_event(capacity=1)
    _create(client)

    r = client.post("/api/v1/registrations",
                    json={"user_id": other_user, "event_id": EVENT_ID})

    assert r.status_code == 409, r.data
    assert r.get_json()["error"]["code"] == "EVENT_FULL"


@pytest.mark.req("REQ-REG-B09")
@responses.activate
def test_post_dependency_connection_error_503(client):
    responses.add(responses.GET, _user_url(), body=requests.ConnectionError("refused"))

    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})

    assert r.status_code == 503, r.data
    assert r.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


@pytest.mark.req("REQ-REG-B09")
@responses.activate
def test_post_dependency_5xx_503(client):
    _mock_user()
    responses.add(responses.GET, _event_url(), status=502, body="bad gateway")

    r = client.post("/api/v1/registrations",
                    json={"user_id": USER_ID, "event_id": EVENT_ID})

    assert r.status_code == 503, r.data
    assert r.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


# -----------------------------------------------------------------------
# GET singola e lista
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-E03")
@responses.activate
def test_get_registration_200(client):
    _mock_user()
    _mock_event()
    created = _create(client)

    r = client.get(f"/api/v1/registrations/{created['id']}")

    assert r.status_code == 200
    assert r.get_json()["id"] == created["id"]


@pytest.mark.req("REQ-REG-E03")
def test_get_registration_404(client):
    r = client.get("/api/v1/registrations/does-not-exist")

    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.req("REQ-REG-E02")
@responses.activate
def test_list_registrations_with_filters(client):
    other_user = "33333333-3333-4333-8333-333333333333"
    other_event = "44444444-4444-4444-8444-444444444444"
    _mock_user()
    _mock_user(other_user)
    _mock_event()
    _mock_event(other_event)
    first = _create(client)
    _create(client, user_id=other_user)
    _create(client, event_id=other_event)

    assert client.get("/api/v1/registrations").get_json()["total"] == 3
    assert client.get(f"/api/v1/registrations?user_id={USER_ID}").get_json()["total"] == 2
    assert client.get(f"/api/v1/registrations?event_id={EVENT_ID}").get_json()["total"] == 2
    assert client.get("/api/v1/registrations?status=confirmed").get_json()["total"] == 3
    assert client.get("/api/v1/registrations?status=cancelled").get_json()["total"] == 0

    page = client.get("/api/v1/registrations?page=1&page_size=2").get_json()
    assert page["page"] == 1 and page["page_size"] == 2 and len(page["items"]) == 2
    assert set(page["items"][0]) == REGISTRATION_KEYS
    assert first["id"] in [i["id"] for i in
                           client.get("/api/v1/registrations").get_json()["items"]]


@pytest.mark.req("REQ-REG-E02")
def test_list_invalid_page_size_422(client):
    assert client.get("/api/v1/registrations?page_size=0").status_code == 422
    assert client.get("/api/v1/registrations?page_size=101").status_code == 422
    assert client.get("/api/v1/registrations?page=0").status_code == 422
    r = client.get("/api/v1/registrations?page=abc")
    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-REG-E02")
def test_list_invalid_status_422(client):
    r = client.get("/api/v1/registrations?status=bogus")

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


# -----------------------------------------------------------------------
# Stats
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B08")
@responses.activate
def test_stats_route_not_shadowed_by_id(client):
    """`/registrations/stats` non deve essere interpretato come la lettura di
    una registrazione con id 'stats' (che darebbe 404)."""
    _mock_user()
    _mock_event(capacity=5)
    _create(client)

    r = client.get(f"/api/v1/registrations/stats?event_id={EVENT_ID}")

    assert r.status_code == 200, r.data
    assert r.get_json() == {"event_id": EVENT_ID, "capacity": 5,
                            "confirmed": 1, "available": 4}


@pytest.mark.req("REQ-REG-B08")
def test_stats_missing_event_id_422(client):
    r = client.get("/api/v1/registrations/stats")

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-REG-B08")
@responses.activate
def test_stats_unknown_event_404(client):
    _mock_event(status=404)

    r = client.get(f"/api/v1/registrations/stats?event_id={EVENT_ID}")

    assert r.status_code == 404, r.data
    assert r.get_json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.req("REQ-REG-B09")
@responses.activate
def test_stats_dependency_down_503(client):
    responses.add(responses.GET, _event_url(), body=requests.ConnectionError("refused"))

    r = client.get(f"/api/v1/registrations/stats?event_id={EVENT_ID}")

    assert r.status_code == 503, r.data
    assert r.get_json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


# -----------------------------------------------------------------------
# PATCH
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-E04")
@responses.activate
def test_patch_200(client):
    _mock_user()
    _mock_event()
    created = _create(client)

    r = client.patch(f"/api/v1/registrations/{created['id']}",
                     json={"status": "cancelled"})

    assert r.status_code == 200, r.data
    assert r.get_json()["status"] == "cancelled"


@pytest.mark.req("REQ-REG-E04")
def test_patch_404(client):
    r = client.patch("/api/v1/registrations/missing", json={"status": "cancelled"})

    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.req("REQ-REG-E04")
def test_patch_invalid_status_422(client):
    r = client.patch("/api/v1/registrations/whatever", json={"status": "bogus"})

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-REG-E04")
def test_patch_missing_status_422(client):
    r = client.patch("/api/v1/registrations/whatever", json={})

    assert r.status_code == 422
    assert r.get_json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-REG-B07")
@responses.activate
def test_patch_invalid_transition_422(client):
    _mock_user()
    _mock_event()
    created = _create(client)
    client.patch(f"/api/v1/registrations/{created['id']}", json={"status": "cancelled"})

    r = client.patch(f"/api/v1/registrations/{created['id']}",
                     json={"status": "confirmed"})

    assert r.status_code == 422, r.data
    assert r.get_json()["error"]["code"] == "INVALID_STATUS_TRANSITION"


# -----------------------------------------------------------------------
# PUT non previsto e DELETE
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-E06")
def test_put_returns_405(client):
    r = client.put("/api/v1/registrations/whatever", json={"status": "cancelled"})

    assert r.status_code == 405
    error = r.get_json()["error"]
    assert error["code"] == "METHOD_NOT_ALLOWED"
    assert isinstance(error["message"], str) and error["message"]


@pytest.mark.req("REQ-REG-E05")
@responses.activate
def test_delete_204_then_404(client):
    _mock_user()
    _mock_event()
    created = _create(client)

    assert client.delete(f"/api/v1/registrations/{created['id']}").status_code == 204
    assert client.get(f"/api/v1/registrations/{created['id']}").status_code == 404


@pytest.mark.req("REQ-REG-E05")
def test_delete_unknown_404(client):
    r = client.delete("/api/v1/registrations/missing")

    assert r.status_code == 404
    assert r.get_json()["error"]["code"] == "NOT_FOUND"
