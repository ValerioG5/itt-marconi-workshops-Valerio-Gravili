"""T-18 — Test di integrazione con user-service, event-service e
registration-service reali.

Nessun mock: tre processi veri su porte libere, concatenati via variabili
d'ambiente. È l'unico livello in cui la regola di capienza viene esercitata
end-to-end attraverso i contratti reali dei tre servizi.
"""

import os
import socket
import subprocess
import sys
import time
import uuid

import pytest
import requests

_USER_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "user-service"))
_EVENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "event-service"))
_REG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_service(service_dir, port, extra_env=None):
    env = dict(os.environ)
    env["PORT"] = str(port)
    env["STORAGE_BACKEND"] = "memory"
    env["PYTHONPATH"] = service_dir + os.pathsep + env.get("PYTHONPATH", "")
    if extra_env:
        env.update(extra_env)

    return subprocess.Popen(
        [sys.executable, "-m", "app"],
        cwd=service_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def _wait_healthy(proc, base_url, name, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
            raise RuntimeError(f"{name} exited early:\n{out}")
        try:
            r = requests.get(f"{base_url}/health", timeout=1)
            if r.status_code == 200:
                return
        except requests.exceptions.RequestException:
            time.sleep(0.2)
    proc.terminate()
    raise RuntimeError(f"{name} did not become ready within {timeout}s")


def _stop(proc):
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


@pytest.fixture(scope="module")
def live_stack():
    user_port = _free_port()
    user_url = f"http://127.0.0.1:{user_port}"
    user_proc = _start_service(_USER_DIR, user_port)
    _wait_healthy(user_proc, user_url, "user-service")

    event_port = _free_port()
    event_url = f"http://127.0.0.1:{event_port}"
    event_proc = _start_service(_EVENT_DIR, event_port, {"USER_SERVICE_URL": user_url})
    try:
        _wait_healthy(event_proc, event_url, "event-service")
    except Exception:
        _stop(user_proc)
        raise

    reg_port = _free_port()
    reg_url = f"http://127.0.0.1:{reg_port}"
    reg_proc = _start_service(
        _REG_DIR, reg_port,
        {"USER_SERVICE_URL": user_url, "EVENT_SERVICE_URL": event_url},
    )
    try:
        _wait_healthy(reg_proc, reg_url, "registration-service")
    except Exception:
        _stop(event_proc)
        _stop(user_proc)
        raise

    yield {"user_url": user_url, "event_url": event_url, "reg_url": reg_url,
           "event_proc": event_proc}

    _stop(reg_proc)
    _stop(event_proc)
    _stop(user_proc)


# -----------------------------------------------------------------------
# Helpers di setup sui servizi reali
# -----------------------------------------------------------------------

def _create_user(user_url, role, email_prefix):
    """Email univoca per evitare 409 EMAIL_ALREADY_EXISTS fra i test."""
    email = f"{email_prefix}.{uuid.uuid4().hex[:8]}@techconf.test"
    r = requests.post(
        f"{user_url}/api/v1/users",
        json={"first_name": "Ada", "last_name": "Lovelace", "email": email, "role": role},
        timeout=5,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_event(event_url, organizer_id, capacity=10, price=149.00):
    r = requests.post(
        f"{event_url}/api/v1/events",
        json={"title": "PyConf Italia", "organizer_id": organizer_id,
              "venue": "Auditorium", "city": "Roma",
              "start_date": "2026-10-15", "end_date": "2026-10-16",
              "capacity": capacity, "price": price},
        timeout=10,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _create_published_event(event_url, organizer_id, capacity=10, price=149.00):
    event = _create_event(event_url, organizer_id, capacity, price)
    r = requests.patch(
        f"{event_url}/api/v1/events/{event['id']}",
        json={"status": "published"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _register(reg_url, user_id, event_id):
    return requests.post(
        f"{reg_url}/api/v1/registrations",
        json={"user_id": user_id, "event_id": event_id},
        timeout=10,
    )


def _stats(reg_url, event_id):
    r = requests.get(
        f"{reg_url}/api/v1/registrations/stats",
        params={"event_id": event_id},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    return r.json()


# -----------------------------------------------------------------------
# Scenario limite completo
# -----------------------------------------------------------------------

@pytest.mark.req("REQ-REG-B01", "REQ-REG-B02", "REQ-REG-B03", "REQ-REG-B04",
                 "REQ-REG-B05", "REQ-REG-B07", "REQ-REG-B08", "REQ-REG-E01",
                 "REQ-REG-E04")
def test_real_capacity_scenario(live_stack):
    """Riempimento, rifiuto a capienza esaurita, cancellazione che libera il
    posto e nuova iscrizione: tutto attraverso i tre servizi reali."""
    reg_url = live_stack["reg_url"]

    organizer = _create_user(live_stack["user_url"], "organizer", "organizer")
    event = _create_published_event(live_stack["event_url"], organizer["id"], capacity=2)
    attendees = [
        _create_user(live_stack["user_url"], "attendee", f"attendee{i}")
        for i in range(4)
    ]

    first = _register(reg_url, attendees[0]["id"], event["id"])
    assert first.status_code == 201, first.text

    second = _register(reg_url, attendees[1]["id"], event["id"])
    assert second.status_code == 201, second.text

    third = _register(reg_url, attendees[2]["id"], event["id"])
    assert third.status_code == 409, third.text
    assert third.json()["error"]["code"] == "EVENT_FULL"

    stats = _stats(reg_url, event["id"])
    assert stats["capacity"] == 2
    assert stats["confirmed"] == 2
    assert stats["available"] == 0

    cancelled = requests.patch(
        f"{reg_url}/api/v1/registrations/{first.json()['id']}",
        json={"status": "cancelled"},
        timeout=10,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    stats = _stats(reg_url, event["id"])
    assert stats["confirmed"] == 1
    assert stats["available"] == 1

    fourth = _register(reg_url, attendees[3]["id"], event["id"])
    assert fourth.status_code == 201, fourth.text

    stats = _stats(reg_url, event["id"])
    assert stats["confirmed"] == 2
    assert stats["available"] == 0


@pytest.mark.req("REQ-REG-B01")
def test_real_user_not_found(live_stack):
    r = _register(live_stack["reg_url"], str(uuid.uuid4()), str(uuid.uuid4()))

    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "REFERENCE_NOT_FOUND"


@pytest.mark.req("REQ-REG-B03")
def test_real_event_not_published(live_stack):
    organizer = _create_user(live_stack["user_url"], "organizer", "organizer.draft")
    attendee = _create_user(live_stack["user_url"], "attendee", "attendee.draft")
    draft = _create_event(live_stack["event_url"], organizer["id"], capacity=10)
    assert draft["status"] == "draft"

    r = _register(live_stack["reg_url"], attendee["id"], draft["id"])

    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "EVENT_NOT_OPEN"


@pytest.mark.req("REQ-REG-B06")
def test_real_amount_from_event_price(live_stack):
    organizer = _create_user(live_stack["user_url"], "organizer", "organizer.price")
    attendee = _create_user(live_stack["user_url"], "attendee", "attendee.price")
    event = _create_published_event(live_stack["event_url"], organizer["id"],
                                    capacity=5, price=99.50)

    r = _register(live_stack["reg_url"], attendee["id"], event["id"])

    assert r.status_code == 201, r.text
    assert r.json()["amount"] == 99.50


@pytest.mark.req("REQ-REG-B09")
def test_real_zzz_dependency_down(live_stack):
    """Spegne event-service: deve essere l'ultimo test del modulo, perché
    rimuove una dipendenza condivisa dagli altri (nome con zzz per l'ordine)."""
    attendee = _create_user(live_stack["user_url"], "attendee", "attendee.down")
    _stop(live_stack["event_proc"])
    time.sleep(0.5)

    r = _register(live_stack["reg_url"], attendee["id"], str(uuid.uuid4()))

    assert r.status_code == 503, r.text
    assert r.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
