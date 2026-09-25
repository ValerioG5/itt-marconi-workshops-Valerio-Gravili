"""T-18 — Test di integrazione con user-service ed event-service reali.

Nessun mock: due processi veri su porte libere, con event-service configurato
per puntare alla porta effettiva di user-service. È l'unico livello in cui il
contratto fra i due servizi viene esercitato end-to-end.
"""

import os
import socket
import subprocess
import sys
import time
import uuid

import pytest
import requests

_USER_SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "user-service"))
_EVENT_SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _payload(**kw):
    d = {"title": "PyConf Italia", "organizer_id": "org1", "venue": "Auditorium",
         "city": "Roma", "start_date": "2026-10-15", "end_date": "2026-10-16",
         "capacity": 100, "price": 149.00}
    d.update(kw)
    return d


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
    user_proc = _start_service(_USER_SERVICE_DIR, user_port)
    _wait_healthy(user_proc, user_url, "user-service")

    event_port = _free_port()
    event_url = f"http://127.0.0.1:{event_port}"
    event_proc = _start_service(
        _EVENT_SERVICE_DIR, event_port, {"USER_SERVICE_URL": user_url}
    )
    try:
        _wait_healthy(event_proc, event_url, "event-service")
    except Exception:
        _stop(user_proc)
        raise

    yield {"user_url": user_url, "event_url": event_url, "user_proc": user_proc}

    _stop(event_proc)
    _stop(user_proc)


def _create_user(user_url, role, email):
    r = requests.post(
        f"{user_url}/api/v1/users",
        json={"first_name": "Ada", "last_name": "Lovelace", "email": email, "role": role},
        timeout=5,
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.mark.req("REQ-EVT-B01", "REQ-EVT-B02", "REQ-EVT-E01")
def test_real_create_event_with_valid_organizer(live_stack):
    organizer = _create_user(live_stack["user_url"], "organizer", "organizer.real@b.com")

    r = requests.post(
        f"{live_stack['event_url']}/api/v1/events",
        json=_payload(organizer_id=organizer["id"]),
        timeout=10,
    )

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["organizer_id"] == organizer["id"]
    assert r.headers["Location"] == f"/api/v1/events/{body['id']}"


@pytest.mark.req("REQ-EVT-B01")
def test_real_organizer_not_found(live_stack):
    r = requests.post(
        f"{live_stack['event_url']}/api/v1/events",
        json=_payload(organizer_id=str(uuid.uuid4())),
        timeout=10,
    )

    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "REFERENCE_NOT_FOUND"


@pytest.mark.req("REQ-EVT-B02")
def test_real_invalid_organizer_role(live_stack):
    attendee = _create_user(live_stack["user_url"], "attendee", "attendee.real@b.com")

    r = requests.post(
        f"{live_stack['event_url']}/api/v1/events",
        json=_payload(organizer_id=attendee["id"]),
        timeout=10,
    )

    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "INVALID_ORGANIZER"


@pytest.mark.req("REQ-EVT-B05")
def test_real_zzz_user_service_down(live_stack):
    """Spegne user-service: deve essere l'ultimo test del modulo, perché
    rimuove una dipendenza condivisa dagli altri (nome con zzz per l'ordine)."""
    _stop(live_stack["user_proc"])
    time.sleep(0.5)

    r = requests.post(
        f"{live_stack['event_url']}/api/v1/events",
        json=_payload(organizer_id=str(uuid.uuid4())),
        timeout=10,
    )

    assert r.status_code == 503, r.text
    assert r.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"
