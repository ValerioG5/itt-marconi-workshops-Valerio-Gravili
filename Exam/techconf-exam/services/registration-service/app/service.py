class RegistrationService:
    """Business logic delle registrazioni (REQ-REG-B*).

    Stub: i metodi di dominio vengono implementati in T-08 e T-09.
    """

    def __init__(self, repository, user_client, event_client):
        self.repository = repository
        self.user_client = user_client
        self.event_client = event_client
