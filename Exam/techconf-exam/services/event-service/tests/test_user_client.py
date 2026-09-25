"""T-13 — Test unitari di UserClient.

Copre la tabella di error mapping: ogni riga della tabella corrisponde a un
test, così una regressione nell'ordine dei controlli (404 prima di 5xx) si
manifesta subito.
"""

import pytest
import requests
import responses

from app.clients.user_client import UserClient
from app.repository.base import (
    DependencyUnavailableError,
    OrganizerNotFoundError,
)

BASE_URL = "http://user-service.test:5001"

ORGANIZER = {
    "id": "org1",
    "role": "organizer",
    "first_name": "A",
    "last_name": "B",
    "email": "a@b.c",
    "company": None,
    "created_at": "2025-01-01T00:00:00Z",
    "updated_at": "2025-01-01T00:00:00Z",
}


@pytest.fixture
def client():
    return UserClient(BASE_URL, timeout=2)


def _url(user_id="org1"):
    return f"{BASE_URL}/api/v1/users/{user_id}"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-B01")
@responses.activate
def test_get_user_ok(client):
    responses.add(responses.GET, _url(), json=ORGANIZER, status=200)

    user = client.get_user("org1")
    assert user["id"] == "org1"
    assert user["role"] == "organizer"


# ---------------------------------------------------------------------------
# 404 → OrganizerNotFoundError (deve precedere il controllo su 5xx)
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-B01")
@responses.activate
def test_get_user_404_raises_organizer_not_found(client):
    responses.add(
        responses.GET,
        _url("ghost"),
        json={"error": {"code": "NOT_FOUND", "message": "nope"}},
        status=404,
    )

    with pytest.raises(OrganizerNotFoundError):
        client.get_user("ghost")


# ---------------------------------------------------------------------------
# Guasti della dipendenza → DependencyUnavailableError
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_get_user_500_raises_dependency_unavailable(client):
    responses.add(responses.GET, _url(), status=500)

    with pytest.raises(DependencyUnavailableError):
        client.get_user("org1")


@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_get_user_503_raises_dependency_unavailable(client):
    responses.add(responses.GET, _url(), status=503)

    with pytest.raises(DependencyUnavailableError):
        client.get_user("org1")


@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_get_user_connection_error(client):
    responses.add(responses.GET, _url(), body=requests.ConnectionError("refused"))

    with pytest.raises(DependencyUnavailableError):
        client.get_user("org1")


@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_get_user_timeout(client):
    responses.add(responses.GET, _url(), body=requests.Timeout("timed out"))

    with pytest.raises(DependencyUnavailableError):
        client.get_user("org1")


@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_get_user_unexpected_status(client):
    """Uno status né 200 né 404 né 5xx resta un guasto della dipendenza."""
    responses.add(responses.GET, _url(), status=418)

    with pytest.raises(DependencyUnavailableError):
        client.get_user("org1")


# ---------------------------------------------------------------------------
# REQ-EVT-B05 criterio 6 — nessun URL hard-coded
# ---------------------------------------------------------------------------

@pytest.mark.req("REQ-EVT-B05")
@responses.activate
def test_uses_configured_base_url():
    """La base URL configurata viene usata così com'è, con lo slash finale
    normalizzato: l'URL chiamato non deve contenere un doppio slash."""
    configured = "http://other-host:9999/"
    responses.add(
        responses.GET,
        "http://other-host:9999/api/v1/users/org1",
        json=ORGANIZER,
        status=200,
    )

    UserClient(configured, timeout=2).get_user("org1")

    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == "http://other-host:9999/api/v1/users/org1"
