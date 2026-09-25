import os
import socket
import subprocess
import sys
import time

import pytest
import requests

_SERVICE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def live_url():
    port = _free_port()
    env = dict(os.environ)
    env["PORT"] = str(port)
    env["STORAGE_BACKEND"] = "memory"
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
            # process died; capture output
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


@pytest.mark.req("REQ-USR-E01", "REQ-USR-E03")
def test_integration_create_and_get(live_url):
    payload = {"first_name": "Ada", "last_name": "Lovelace", "email": "integ1@b.com"}
    r = requests.post(f"{live_url}/api/v1/users", json=payload, timeout=5)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["email"] == "integ1@b.com"

    r2 = requests.get(f"{live_url}/api/v1/users/{created['id']}", timeout=5)
    assert r2.status_code == 200
    assert r2.json()["id"] == created["id"]


@pytest.mark.req("REQ-USR-E03")
def test_integration_get_not_found(live_url):
    r = requests.get(f"{live_url}/api/v1/users/nonexistent-id", timeout=5)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


@pytest.mark.req("REQ-USR-B01")
def test_integration_duplicate_email(live_url):
    payload = {"first_name": "Eve", "last_name": "M", "email": "dup@b.com"}
    r1 = requests.post(f"{live_url}/api/v1/users", json=payload, timeout=5)
    assert r1.status_code == 201
    r2 = requests.post(f"{live_url}/api/v1/users", json={**payload, "email": "DUP@B.COM"}, timeout=5)
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"


@pytest.mark.req("REQ-USR-00")
def test_integration_health(live_url):
    r = requests.get(f"{live_url}/health", timeout=5)
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "user-service"
