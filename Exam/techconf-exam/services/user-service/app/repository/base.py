from abc import ABC, abstractmethod


class UserNotFoundError(Exception):
    """Sollevata quando un utente non viene trovato per id."""
    pass


class EmailAlreadyExistsError(Exception):
    """Sollevata quando si tenta di salvare un'email già registrata."""
    pass


class AbstractUserRepository(ABC):

    @abstractmethod
    def save(self, user: dict) -> dict:
        """Inserisce un nuovo utente. Restituisce l'utente salvato."""

    @abstractmethod
    def find_by_id(self, user_id: str) -> dict | None:
        """Restituisce il dizionario utente o None se non esiste."""

    @abstractmethod
    def find_by_email(self, email: str) -> dict | None:
        """Ricerca per email (già normalizzata in minuscolo). Restituisce None se non esiste."""

    @abstractmethod
    def list_all(self, role: str | None, email: str | None) -> list[dict]:
        """Restituisce tutti gli utenti, opzionalmente filtrati per role e/o email."""

    @abstractmethod
    def update(self, user: dict) -> dict:
        """Sovrascrive l'utente esistente con i dati forniti. Restituisce il dizionario aggiornato."""

    @abstractmethod
    def delete(self, user_id: str) -> None:
        """Rimuove l'utente. Solleva UserNotFoundError se non esiste."""
