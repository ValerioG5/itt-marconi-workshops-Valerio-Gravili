import requests

from app.repository.base import (
    DependencyUnavailableError,
    OrganizerNotFoundError,
)


class UserClient:
    """Client HTTP verso user-service.

    Unico punto del servizio che conosce `requests`. Incapsula il timeout
    fisso e l'error mapping definito in platform-standards.md:

        404              -> OrganizerNotFoundError    => 422 REFERENCE_NOT_FOUND
        timeout          -> DependencyUnavailableError => 503
        connection error -> DependencyUnavailableError => 503
        5xx              -> DependencyUnavailableError => 503
    """

    def __init__(self, base_url: str, timeout: int = 2):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_user(self, user_id: str) -> dict:
        """Recupera un utente da user-service.

        Raises:
            OrganizerNotFoundError: l'utente non esiste (404 remoto).
            DependencyUnavailableError: user-service non raggiungibile,
                timeout, o risposta 5xx / inattesa.
        """
        url = f"{self._base_url}/api/v1/users/{user_id}"
        try:
            resp = requests.get(url, timeout=self._timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise DependencyUnavailableError("user-service unreachable") from exc
        except requests.RequestException as exc:
            raise DependencyUnavailableError("user-service request failed") from exc

        # L'ordine dei controlli conta: 404 va valutato prima di >= 500,
        # altrimenti un utente inesistente verrebbe confuso con un guasto.
        if resp.status_code == 404:
            raise OrganizerNotFoundError(user_id)
        if resp.status_code >= 500:
            raise DependencyUnavailableError(
                f"user-service returned {resp.status_code}"
            )
        if resp.status_code != 200:
            raise DependencyUnavailableError(
                f"user-service returned unexpected status {resp.status_code}"
            )

        return resp.json()
