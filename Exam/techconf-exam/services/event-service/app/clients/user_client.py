class UserClient:
    """Client HTTP verso user-service. Implementato in T-06."""

    def __init__(self, base_url: str, timeout: int = 2):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_user(self, user_id: str) -> dict:
        raise NotImplementedError
