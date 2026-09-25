"""T-17 — Test di integrazione con il solo registration-service in esecuzione.

USER_SERVICE_URL ed EVENT_SERVICE_URL puntano a porte chiuse: serve a provare
che una dipendenza giù produce 503 e non un 422, e che health, validazione,
lettura e method-not-allowed non dipendono da esse.
"""

import os
import socket
import subprocess
import sys
import time

import pytest
import requests

_SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

USER_ID = "11111111-1111-4111-8111-111111111111"
EVENT_ID = "22222222-2222-4222-8222-222222222222"


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def live_url():
    port = _free_port()
    # porte liberate subito: nessuno è in ascolto, quindi le connessioni verso
    # user-service ed event-service verranno rifiutate
    closed_user_port = _free_port()
    closed_event_port = _free_port()

    env = dict(os.environ)
    env["PORT"] = str(port)
    env["STORAGE_BACKEND"] = "memory"
    env["USER_SERVICE_URL"] = f"http://127.0.0.1:{closed_user_port}"
    env["EVENT_SERVICE_URL"] = f"http://127.0.0.1:{closed_event_port}"
    env["PYTHONPATH"] = _SERVICE_DIR + os.pathsep + env.get("PYTHONPATH", "")

    proc = subprocess.Popen(
        [sys.executable, "-m", "app"],
        cwd=_SERVICE_DIR,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    base_url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 15
    ready = False
    while time.time() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
            raise RuntimeError(f"Service process exited early:\n{out}")
        try:
            r = requests.get(f"{base_url}/health", timeout=1)
            if r.status_code == 200:
                ready = True
                break
        except requests.exceptions.RequestException:
            time.sleep(0.2)

    if not ready:
        proc.terminate()
        raise RuntimeError("Service did not become ready within timeout")

    yield base_url

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@pytest.mark.req("REQ-REG-00")
def test_integration_health(live_url):
    r = requests.get(f"{live_url}/health", timeout=5)

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "registration-service"


@pytest.mark.req("REQ-REG-B09")
def test_integration_dependency_down_returns_503(live_url):
    r = requests.post(f"{live_url}/api/v1/registrations",
                      json={"user_id": USER_ID, "event_id": EVENT_ID}, timeout=10)

    assert r.status_code == 503, r.text
    assert r.json()["error"]["code"] == "DEPENDENCY_UNAVAILABLE"


@pytest.mark.req("REQ-REG-F02")
def test_integration_validation_error_without_dependency(live_url):
    """Payload invalido: 422, non 503, anche con entrambe le dipendenze giù."""
    r = requests.post(f"{live_url}/api/v1/registrations",
                      json={"user_id": ""}, timeout=10)

    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


@pytest.mark.req("REQ-REG-E03")
def test_integration_get_not_found(live_url):
    r = requests.get(f"{live_url}/api/v1/registrations/nonexistent-id", timeout=5)

    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.req("REQ-REG-E06")
def test_integration_put_405(live_url):
    r = requests.put(f"{live_url}/api/v1/registrations/{EVENT_ID}",
                     json={"status": "cancelled"}, timeout=5)

    assert r.status_code == 405, r.text
    assert r.json()["error"]["code"] == "METHOD_NOT_ALLOWED"
