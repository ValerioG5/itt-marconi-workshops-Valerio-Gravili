class EventService:
    """Business logic. Implementata in T-08/T-09."""

    def __init__(self, repository, user_client):
        self.repository = repository
        self.user_client = user_client
