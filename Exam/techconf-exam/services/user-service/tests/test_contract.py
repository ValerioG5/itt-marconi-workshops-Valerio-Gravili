import json
import os
import sys

import pytest

# Aggiungi la workspace root (techconf-exam/) a sys.path per importare contracts.validator
# tests/ -> .. -> user-service/ -> .. -> services/ -> .. -> techconf-exam/
_WORKSPACE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
sys.path.insert(0, _WORKSPACE_ROOT)

from contracts.validator import assert_matches_contract
from app import create_app
from app.repository.memory import MemoryUserRepository


@pytest.fixture
def client():
    app = create_app(repository=MemoryUserRepository())
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


def _post_user(client, email="contract@test.com"):
    r = client.post("/api/v1/users", json={
        "first_name": "Contract",
        "last_name": "Test",
        "email": email,
    })
    assert r.status_code == 201, f"Setup failed: {r.data}"
    return json.loads(r.data)


# -----------------------------------------------------------------------
# Ogni test chiama assert_matches_contract per verificare la risposta
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-C01")
def test_contract_health(client):
    r = client.get("/health")
    assert_matches_contract("user-service", "GET", "/health", _adapt(r))


@pytest.mark.req("REQ-USR-C01")
def test_contract_post_user(client):
    r = client.post("/api/v1/users", json={
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": "ada.contract@b.com",
    })
    assert r.status_code == 201
    assert_matches_contract("user-service", "POST", "/api/v1/users", _adapt(r))


@pytest.mark.req("REQ-USR-C01")
def test_contract_get_user(client):
    created = _post_user(client, "get.contract@b.com")
    r = client.get(f"/api/v1/users/{created['id']}")
    assert_matches_contract("user-service", "GET", f"/api/v1/users/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-USR-C01")
def test_contract_list_users(client):
    _post_user(client, "list.contract@b.com")
    r = client.get("/api/v1/users")
    assert_matches_contract("user-service", "GET", "/api/v1/users", _adapt(r))


@pytest.mark.req("REQ-USR-C01")
def test_contract_put_user(client):
    created = _post_user(client, "put.contract@b.com")
    r = client.put(f"/api/v1/users/{created['id']}", json={
        "first_name": "Updated",
        "last_name": "User",
        "email": "put.contract@b.com",
    })
    assert_matches_contract("user-service", "PUT", f"/api/v1/users/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-USR-C01")
def test_contract_patch_user(client):
    created = _post_user(client, "patch.contract@b.com")
    r = client.patch(f"/api/v1/users/{created['id']}", json={"company": "Test Co"})
    assert_matches_contract("user-service", "PATCH", f"/api/v1/users/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-USR-C01")
def test_contract_delete_user(client):
    created = _post_user(client, "delete.contract@b.com")
    r = client.delete(f"/api/v1/users/{created['id']}")
    assert_matches_contract("user-service", "DELETE", f"/api/v1/users/{created['id']}", _adapt(r))


@pytest.mark.req("REQ-USR-C01")
def test_contract_error_404(client):
    r = client.get("/api/v1/users/nonexistent-id-12345")
    assert r.status_code == 404
    assert_matches_contract("user-service", "GET", "/api/v1/users/nonexistent-id-12345", _adapt(r))
