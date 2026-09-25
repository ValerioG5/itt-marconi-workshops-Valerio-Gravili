import json
import pytest
from app import create_app
from app.repository.memory import MemoryUserRepository


@pytest.fixture
def client():
    """Flask test client con MemoryUserRepository fresco per ogni test."""
    app = create_app(repository=MemoryUserRepository())
    app.config["TESTING"] = True
    return app.test_client()


def _post_user(client, email="ada@b.com", **kwargs):
    """Helper: crea un utente valido e restituisce il body JSON."""
    data = {"first_name": "Ada", "last_name": "Lovelace", "email": email}
    data.update(kwargs)
    r = client.post("/api/v1/users", json=data)
    return r, json.loads(r.data)


# -----------------------------------------------------------------------
# Health  (REQ-USR-00)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-00")
def test_health_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = json.loads(r.data)
    assert body["status"] == "ok"
    assert body["service"] == "user-service"


# -----------------------------------------------------------------------
# POST /api/v1/users  (REQ-USR-E01)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E01")
def test_post_user_201(client):
    r, body = _post_user(client, email="ADA@B.COM")
    assert r.status_code == 201
    assert body["email"] == "ada@b.com"
    assert body["role"] == "attendee"
    assert body["id"]
    assert body["created_at"] and body["updated_at"]
    assert "Location" in r.headers
    assert r.headers["Location"] == f"/api/v1/users/{body['id']}"


# -----------------------------------------------------------------------
# Validazione input  (REQ-USR-F02)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-F02")
def test_post_user_422_missing_field(client):
    r = client.post("/api/v1/users", json={"first_name": "Ada", "email": "x@x.com"})
    assert r.status_code == 422
    assert json.loads(r.data)["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-USR-F02")
def test_post_user_422_invalid_email(client):
    r = client.post("/api/v1/users", json={"first_name": "Ada", "last_name": "L", "email": "notanemail"})
    assert r.status_code == 422
    assert json.loads(r.data)["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-USR-F02")
def test_post_user_422_invalid_role(client):
    r = client.post("/api/v1/users", json={"first_name": "Ada", "last_name": "L", "email": "x@x.com", "role": "god"})
    assert r.status_code == 422
    assert json.loads(r.data)["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-USR-F02")
def test_post_user_400_malformed_json(client):
    r = client.post("/api/v1/users", data="{bad json", content_type="application/json")
    assert r.status_code == 400
    assert json.loads(r.data)["error"]["code"] == "MALFORMED_JSON"


# -----------------------------------------------------------------------
# Email duplicata  (REQ-USR-B01)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-B01")
def test_post_user_409_duplicate_email(client):
    _post_user(client, email="ada@b.com")
    r, body = _post_user(client, email="ADA@B.COM")
    assert r.status_code == 409
    assert body["error"]["code"] == "EMAIL_ALREADY_EXISTS"


# -----------------------------------------------------------------------
# GET /api/v1/users/{id}  (REQ-USR-E03)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E03")
def test_get_user_200(client):
    _, created = _post_user(client)
    r = client.get(f"/api/v1/users/{created['id']}")
    assert r.status_code == 200
    assert json.loads(r.data)["id"] == created["id"]


@pytest.mark.req("REQ-USR-E03")
def test_get_user_404(client):
    r = client.get("/api/v1/users/nonexistent-id")
    assert r.status_code == 404
    assert json.loads(r.data)["error"]["code"] == "NOT_FOUND"


# -----------------------------------------------------------------------
# GET /api/v1/users  (REQ-USR-E02)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E02")
def test_list_users_200(client):
    _post_user(client, email="a@b.com")
    r = client.get("/api/v1/users")
    assert r.status_code == 200
    body = json.loads(r.data)
    assert "items" in body and "total" in body and "page" in body and "page_size" in body
    assert body["total"] >= 1


@pytest.mark.req("REQ-USR-E02")
def test_list_users_422_bad_page_size(client):
    r = client.get("/api/v1/users?page_size=200")
    assert r.status_code == 422
    assert json.loads(r.data)["error"]["code"] == "VALIDATION_ERROR"


# -----------------------------------------------------------------------
# PUT /api/v1/users/{id}  (REQ-USR-E04)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E04")
def test_put_user_200(client):
    _, created = _post_user(client)
    r = client.put(f"/api/v1/users/{created['id']}",
                   json={"first_name": "Eve", "last_name": "M", "email": "ada@b.com", "role": "speaker"})
    assert r.status_code == 200
    body = json.loads(r.data)
    assert body["first_name"] == "Eve"
    assert body["role"] == "speaker"
    assert body["updated_at"]


@pytest.mark.req("REQ-USR-E04")
def test_put_user_404(client):
    r = client.put("/api/v1/users/nonexistent",
                   json={"first_name": "X", "last_name": "Y", "email": "x@x.com"})
    assert r.status_code == 404


# -----------------------------------------------------------------------
# PATCH /api/v1/users/{id}  (REQ-USR-E05)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E05")
def test_patch_user_200(client):
    _, created = _post_user(client)
    r = client.patch(f"/api/v1/users/{created['id']}", json={"company": "ACME"})
    assert r.status_code == 200
    body = json.loads(r.data)
    assert body["company"] == "ACME"
    assert body["first_name"] == created["first_name"]  # unchanged


# -----------------------------------------------------------------------
# DELETE /api/v1/users/{id}  (REQ-USR-E06)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-USR-E06")
def test_delete_user_204(client):
    _, created = _post_user(client)
    r = client.delete(f"/api/v1/users/{created['id']}")
    assert r.status_code == 204
    # verifica che GET successivo restituisca 404
    r2 = client.get(f"/api/v1/users/{created['id']}")
    assert r2.status_code == 404
