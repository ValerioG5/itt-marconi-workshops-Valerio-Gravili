"""T-13 — Test unitari dei client HTTP verso user-service ed event-service.

I due client condividono `BaseHttpClient`, quindi ogni scenario di errore è
parametrizzato su entrambi: se il mapping regredisse per uno solo, la
parametrizzazione lo rende evidente.
"""

import pytest
import requests
import responses

from app.clients.event_client import EventClient
from app.clients.user_client import UserClient
from app.repository.base import (
    DependencyUnavailableError,
    ReferenceNotFoundError,
)

_BASE = "http://dependency.test"
_RID = "res-1"


def _user(base=_BASE):
    return UserClient(base, timeout=1)


def _event(base=_BASE):
    return EventClient(base, timeout=1)


def _call_user(client):
    return client.get_user(_RID)


def _call_event(client):
    return client.get_event(_RID)


# (factory, invocazione, segmento di path, payload di esempio)
CLIENTS = [
    pytest.param(_user, _call_user, "users", {"id": _RID, "role": "attendee"}, id="user"),
    pytest.param(_event, _call_event, "events", {"id": _RID, "capacity": 10}, id="event"),
]


def _url(segment):
    return f"{_BASE}/api/v1/{segment}/{_RID}"


# -----------------------------------------------------------------------
# Happy path
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B01", "REQ-REG-B02")
@pytest.mark.parametrize("factory,call,segment,payload", CLIENTS)
@responses.activate
def test_client_returns_dict_on_200(factory, call, segment, payload):
    responses.add(responses.GET, _url(segment), json=payload, status=200)

    assert call(factory()) == payload


# -----------------------------------------------------------------------
# Error mapping
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B01", "REQ-REG-B02")
@pytest.mark.parametrize("factory,call,segment,payload", CLIENTS)
@responses.activate
def test_client_404_raises_reference_not_found(factory, call, segment, payload):
    responses.add(responses.GET, _url(segment), status=404,
                  json={"error": {"code": "NOT_FOUND", "message": "nope"}})

    with pytest.raises(ReferenceNotFoundError):
        call(factory())


@pytest.mark.req("REQ-REG-B09")
@pytest.mark.parametrize("factory,call,segment,payload", CLIENTS)
@responses.activate
def test_client_500_raises_dependency_unavailable(factory, call, segment, payload):
    responses.add(responses.GET, _url(segment), status=500, body="boom")

    with pytest.raises(DependencyUnavailableError):
        call(factory())


@pytest.mark.req("REQ-REG-B09")
@pytest.mark.parametrize("factory,call,segment,payload", CLIENTS)
@responses.activate
def test_client_503_raises_dependency_unavailable(factory, call, segment, payload):
    responses.add(responses.GET, _url(segment), status=503, body="unavailable")

    with pytest.raises(DependencyUnavailableError):
        call(factory())


@pytest.mark.req("REQ-REG-B09")
@pytest.mark.parametrize("factory,call,segment,payload", CLIENTS)
@responses.activate
def test_client_connection_error_raises_dependency_unavailable(factory, call, segment, payload):
    responses.add(responses.GET, _url(segment), body=requests.ConnectionError("refused"))

    with pytest.raises(DependencyUnavailableError):
        call(factory())


@pytest.mark.req("REQ-REG-B09")
@pytest.mark.parametrize("factory,call,segment,payload", CLIENTS)
@responses.activate
def test_client_timeout_raises_dependency_unavailable(factory, call, segment, payload):
    responses.add(responses.GET, _url(segment), body=requests.Timeout("too slow"))

    with pytest.raises(DependencyUnavailableError):
        call(factory())


@pytest.mark.req("REQ-REG-B09")
@pytest.mark.parametrize("factory,call,segment,payload", CLIENTS)
@responses.activate
def test_client_unexpected_status_raises_dependency_unavailable(factory, call, segment, payload):
    """Uno status non previsto (418) non è né 404 né 5xx: va comunque trattato
    come dipendenza inaffidabile, non come risorsa assente."""
    responses.add(responses.GET, _url(segment), status=418, body="teapot")

    with pytest.raises(DependencyUnavailableError):
        call(factory())


# -----------------------------------------------------------------------
# Forma dell'URL (slash finale della base normalizzata)
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B01")
@responses.activate
def test_user_client_url_shape():
    responses.add(responses.GET, _url("users"), json={"id": _RID}, status=200)

    UserClient(_BASE + "/", timeout=1).get_user(_RID)

    assert responses.calls[0].request.url == f"{_BASE}/api/v1/users/{_RID}"


@pytest.mark.req("REQ-REG-B02")
@responses.activate
def test_event_client_url_shape():
    responses.add(responses.GET, _url("events"), json={"id": _RID}, status=200)

    EventClient(_BASE + "/", timeout=1).get_event(_RID)

    assert responses.calls[0].request.url == f"{_BASE}/api/v1/events/{_RID}"
