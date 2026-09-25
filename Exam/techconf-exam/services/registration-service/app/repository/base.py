from abc import ABC, abstractmethod


class RegistrationNotFoundError(Exception):
    """Sollevata quando una registrazione non viene trovata per id."""
    pass


class EventNotFoundForStatsError(Exception):
    """Sollevata quando l'evento richiesto da GET /stats non esiste (=> 404)."""
    pass


class ReferenceNotFoundError(Exception):
    """Sollevata quando un riferimento remoto (utente o evento) non esiste (=> 422)."""
    pass


class EventNotOpenError(Exception):
    """Sollevata quando l'evento non è in stato 'published'."""
    pass


class AlreadyRegisteredError(Exception):
    """Sollevata quando esiste già una registrazione 'confirmed' per la coppia utente/evento."""
    pass


class EventFullError(Exception):
    """Sollevata quando la capienza dell'evento è esaurita."""
    pass


class InvalidStatusTransitionError(Exception):
    """Sollevata quando la transizione di stato richiesta non è ammessa."""
    pass


class ValidationError(Exception):
    """Sollevata per violazioni delle regole di validazione dell'input."""
    pass


class DependencyUnavailableError(Exception):
    """Sollevata quando una dipendenza HTTP non è raggiungibile o risponde con errore."""
    pass


class AbstractRegistrationRepository(ABC):
    """Interfaccia di persistenza delle registrazioni.

    Il dict registrazione ha esattamente 7 chiavi:
        id, user_id, event_id, amount, status, created_at, updated_at
    """

    @abstractmethod
    def save(self, registration: dict) -> dict:
        """Inserisce una nuova registrazione. Restituisce la registrazione salvata."""

    @abstractmethod
    def find_by_id(self, registration_id: str) -> dict | None:
        """Restituisce il dizionario registrazione o None se non esiste."""

    @abstractmethod
    def find_confirmed(self, user_id: str, event_id: str) -> dict | None:
        """Restituisce la prima registrazione 'confirmed' per la coppia, oppure None."""

    @abstractmethod
    def count_confirmed(self, event_id: str) -> int:
        """Numero di registrazioni 'confirmed' per l'evento."""

    @abstractmethod
    def list_all(self, user_id: str | None, event_id: str | None,
                 status: str | None) -> list[dict]:
        """Restituisce le registrazioni, opzionalmente filtrate (AND logic)."""

    @abstractmethod
    def update(self, registration: dict) -> dict:
        """Sovrascrive la registrazione esistente. Solleva RegistrationNotFoundError se assente."""

    @abstractmethod
    def delete(self, registration_id: str) -> None:
        """Rimuove la registrazione. Solleva RegistrationNotFoundError se assente."""
