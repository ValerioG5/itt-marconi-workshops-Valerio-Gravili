from abc import ABC, abstractmethod


class EventNotFoundError(Exception):
    """Sollevata quando un evento non viene trovato per id."""
    pass


class OrganizerNotFoundError(Exception):
    """Sollevata quando l'organizer_id non corrisponde a nessun utente in user-service."""
    pass


class InvalidOrganizerError(Exception):
    """Sollevata quando l'utente esiste ma non ha ruolo 'organizer'."""
    pass


class InvalidStatusTransitionError(Exception):
    """Sollevata quando la transizione di stato richiesta non è ammessa."""
    pass


class ValidationError(Exception):
    """Sollevata per violazioni delle regole di business (es. date incoerenti)."""
    pass


class DependencyUnavailableError(Exception):
    """Sollevata quando una dipendenza HTTP non è raggiungibile o risponde con errore."""
    pass


class AbstractEventRepository(ABC):

    @abstractmethod
    def save(self, event: dict) -> dict:
        """Inserisce un nuovo evento. Restituisce l'evento salvato."""

    @abstractmethod
    def find_by_id(self, event_id: str) -> dict | None:
        """Restituisce il dizionario evento o None se non esiste."""

    @abstractmethod
    def list_all(self, status: str | None, city: str | None) -> list[dict]:
        """Restituisce tutti gli eventi, opzionalmente filtrati per status e/o city."""

    @abstractmethod
    def update(self, event: dict) -> dict:
        """Sovrascrive l'evento esistente. Solleva EventNotFoundError se non esiste."""

    @abstractmethod
    def delete(self, event_id: str) -> None:
        """Rimuove l'evento. Solleva EventNotFoundError se non esiste."""
