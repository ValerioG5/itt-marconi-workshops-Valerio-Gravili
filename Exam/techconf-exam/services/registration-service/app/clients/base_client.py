import requests

from app.repository.base import (
    DependencyUnavailableError,
    ReferenceNotFoundError,
)


class BaseHttpClient:
    """Timeout ed error mapping condivisi dai client del servizio.

    Unico modulo del servizio che importa `requests`.

    Mapping (platform-standards.md):
        404              -> ReferenceNotFoundError     => 422 REFERENCE_NOT_FOUND
        timeout          -> DependencyUnavailableError  => 503
        connection error -> DependencyUnavailableError  => 503
        5xx              -> DependencyUnavailableError  => 503
    """

    def __init__(self, base_url: str, timeout: int = 2):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def _get(self, path: str, resource_id: str) -> dict:
        url = f"{self._base_url}{path}/{resource_id}"
        try:
            resp = requests.get(url, timeout=self._timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise DependencyUnavailableError(f"{url} unreachable") from exc
        except requests.RequestException as exc:
            raise DependencyUnavailableError(f"{url} request failed") from exc

        # L'ordine conta: il 404 va valutato prima di >= 500, altrimenti una
        # risorsa inesistente verrebbe confusa con un guasto della dipendenza.
        if resp.status_code == 404:
            raise ReferenceNotFoundError(resource_id)
        if resp.status_code >= 500:
            raise DependencyUnavailableError(f"{url} returned {resp.status_code}")
        if resp.status_code != 200:
            raise DependencyUnavailableError(f"{url} returned {resp.status_code}")
        return resp.json()
