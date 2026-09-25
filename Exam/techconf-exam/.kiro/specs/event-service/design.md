# event-service — Design

Servizio: **event-service**
Contratto: `contracts/openapi/event-service.yaml` ? fonte di verità dell'interfaccia HTTP
Requirements: `.kiro/specs/event-service/requirements.md`
Dipendenze runtime: **user-service** via HTTP

---

## 1. Struttura del package

```
services/event-service/
  app/
    __init__.py            # create_app(): factory Flask + wiring
    __main__.py            # entrypoint: python -m app
    config.py              # lettura env vars (unico punto)
    routes.py              # layer HTTP
    service.py             # business logic REQ-EVT-B*
    clients/
      __init__.py
      user_client.py       # chiamate HTTP verso user-service
    repository/
      __init__.py
      base.py              # AbstractEventRepository + eccezioni
      memory.py
      json_repo.py
      sqlite_repo.py
  tests/
    conftest.py
    test_routes.py
    test_service.py
    test_repository.py
    test_contract.py
    test_integration.py    # event-service da solo (user mockato a livello client)
    test_integration_real.py  # event-service + user-service reali
  requirements.txt
```

Rispetto a `user-service`, la novità è la cartella `clients/`: event-service è il primo servizio che chiama un altro servizio. Come stabilito in `structure.md`, con **una sola** dipendenza HTTP non introduciamo `base_client.py`: la logica di timeout ed error-mapping vive direttamente in `user_client.py`.

---

## 2. Componenti e responsabilità

### 2.1 `config.py`

Unico modulo che legge `os.environ`:

```python
PORT             = int(os.environ.get("PORT", 5002))
USER_SERVICE_URL = os.environ.get("USER_SERVICE_URL", "http://localhost:5001")
STORAGE_BACKEND  = os.environ.get("STORAGE_BACKEND", "memory")
DATA_DIR         = os.environ.get("DATA_DIR", "./data")
DEPENDENCY_TIMEOUT = 2  # secondi, fisso (platform-standards.md)
```

Nessun altro modulo chiama `os.environ.get`. L'URL di user-service **non** è mai scritto nel codice (REQ-EVT-B05 criterio 6).

### 2.2 `__init__.py` — factory

```python
def create_app(repository=None, user_client=None):
    app = Flask(__name__)
    if repository is None:
        repository = _make_repository()
    if user_client is None:
        user_client = UserClient(config.USER_SERVICE_URL, config.DEPENDENCY_TIMEOUT)
    service = EventService(repository, user_client)
    register_routes(app, service)
    return app
```

Due parametri iniettabili: `repository` e `user_client`. Questo è il punto chiave per la testabilità — i test unitari passano un `user_client` finto senza toccare né la rete né le variabili d'ambiente.

### 2.3 `__main__.py`

```python
from app import create_app
from app.config import PORT

if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
```

Bind su `0.0.0.0` (la suite avvia il servizio come sottoprocesso e lo interroga dall'esterno).

### 2.4 `routes.py` — layer HTTP

Responsabilità esclusiva: parsing richiesta ? delega al service ? serializzazione risposta. Nessuna regola di business, nessuna chiamata HTTP verso altri servizi.

| Funzione | Metodo | Path | Requisito |
|---|---|---|---|
| `health()` | GET | `/health` | REQ-EVT-00 |
| `create_event()` | POST | `/api/v1/events` | REQ-EVT-E01 |
| `list_events()` | GET | `/api/v1/events` | REQ-EVT-E02 |
| `get_event(id)` | GET | `/api/v1/events/<id>` | REQ-EVT-E03 |
| `replace_event(id)` | PUT | `/api/v1/events/<id>` | REQ-EVT-E04 |
| `update_event(id)` | PATCH | `/api/v1/events/<id>` | REQ-EVT-E05 |
| `delete_event(id)` | DELETE | `/api/v1/events/<id>` | REQ-EVT-E06 |

Helper privati (duplicati per servizio, come da `structure.md`):
- `_error_response(code, message, status, details=None)`
- `_validate_event_input(data, partial=False) -> list[str]` — i vincoli di lunghezza sui campi stringa obbligatori (`title`, `venue`, `city`) si applicano al valore **trimmed** (BUG-02): `len(value.strip())`, altrimenti una stringa di soli spazi supererebbe il `minLength` del contratto pur essendo semanticamente vuota. Il valore memorizzato resta quello inviato dal client: il `.strip()` decide se accettare, non riscrive il dato
- `_serialize_event(event) -> dict` — solo i 12 campi del contratto
- `_paginate(page_items, page, page_size, total) -> dict`

**Ordine di validazione (importante):** la validazione dei campi avviene **prima** della chiamata a user-service (REQ-EVT-E01 criterio 4). Questo evita chiamate di rete inutili su payload già malformati e rende il 422 di validazione deterministico anche con la dipendenza spenta.

**Mappatura eccezioni ? HTTP:**

| Eccezione da `service.py` | HTTP | `error.code` |
|---|---|---|
| `EventNotFoundError` | 404 | `NOT_FOUND` |
| `OrganizerNotFoundError` | 422 | `REFERENCE_NOT_FOUND` |
| `InvalidOrganizerError` | 422 | `INVALID_ORGANIZER` |
| `InvalidStatusTransitionError` | 422 | `INVALID_STATUS_TRANSITION` |
| `ValidationError` | 422 | `VALIDATION_ERROR` |
| `DependencyUnavailableError` | 503 | `DEPENDENCY_UNAVAILABLE` |

### 2.5 `service.py` — business logic

Riceve due dipendenze iniettate: `repository` (persistenza) e `user_client` (dipendenza HTTP). Non conosce Flask, non conosce `requests`, non sa quale backend è attivo.

| Metodo | Requisiti |
|---|---|
| `create_event(data)` | B01, B02, B03, F01, E01 |
| `list_events(status, city, page, page_size)` | B06, E02 |
| `get_event(id)` | E03 |
| `replace_event(id, data)` | B01, B02, B03, B04, E04 |
| `update_event(id, data)` | B01, B02, B03, B04, E05 |
| `delete_event(id)` | E06 |

**REQ-EVT-B01 + B02 — validazione organizzatore.** Metodo privato condiviso:

```python
def _assert_valid_organizer(self, organizer_id):
    user = self.user_client.get_user(organizer_id)   # solleva le eccezioni mappate
    if user["role"] != "organizer":
        raise InvalidOrganizerError(organizer_id)
```

Il client distingue già "non trovato" da "dipendenza giù"; il service aggiunge solo il controllo sul ruolo. Così la differenza tra `REFERENCE_NOT_FOUND` e `INVALID_ORGANIZER` (REQ-EVT-B02 criterio 4) resta in un unico punto.

**REQ-EVT-B03 — coerenza delle date.** Per `PATCH` la validazione avviene sul **merge** tra dati stored e dati nuovi, non solo sul payload:

```python
merged_start = data.get("start_date", existing["start_date"])
merged_end   = data.get("end_date",   existing["end_date"])
if merged_end < merged_start:       # confronto lessicografico valido su YYYY-MM-DD
    raise ValidationError("end_date must be >= start_date")
```

Il formato `YYYY-MM-DD` rende il confronto lessicografico equivalente al confronto cronologico: nessuna conversione a `date` necessaria.

**REQ-EVT-B04 — macchina a stati.** Tabella esplicita delle transizioni ammesse:

```python
_ALLOWED_TRANSITIONS = {
    "draft":     {"published", "cancelled"},
    "published": {"cancelled"},
    "cancelled": set(),          # stato terminale
}

def _assert_valid_transition(self, current, requested):
    if requested == current:
        return                    # no-op ammesso (criterio 6)
    if requested not in _ALLOWED_TRANSITIONS[current]:
        raise InvalidStatusTransitionError(current, requested)
```

Definire le transizioni come dato (non come catena di `if`) rende il requisito leggibile e il test esaustivo.

---

## 3. Isolamento della chiamata HTTP a user-service

Questa è la parte nuova rispetto a user-service e merita una descrizione dettagliata, perché da essa dipendono i test IT-E02, IT-E03 e IT-E08.

### 3.1 `clients/user_client.py`

Unico punto del servizio che importa `requests`. Nessun altro modulo effettua chiamate HTTP in uscita.

```python
import requests
from app.repository.base import (
    OrganizerNotFoundError,
    DependencyUnavailableError,
)


class UserClient:
    """Client HTTP verso user-service. Unico punto che conosce `requests`."""

    def __init__(self, base_url: str, timeout: int = 2):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def get_user(self, user_id: str) -> dict:
        """Recupera un utente da user-service.

        Error mapping (platform-standards.md):
          404              -> OrganizerNotFoundError  => 422 REFERENCE_NOT_FOUND
          timeout          -> DependencyUnavailableError => 503
          connection error -> DependencyUnavailableError => 503
          5xx              -> DependencyUnavailableError => 503
        """
        url = f"{self._base_url}/api/v1/users/{user_id}"
        try:
            resp = requests.get(url, timeout=self._timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise DependencyUnavailableError("user-service unreachable") from exc
        except requests.RequestException as exc:
            raise DependencyUnavailableError("user-service request failed") from exc

        if resp.status_code == 404:
            raise OrganizerNotFoundError(user_id)
        if resp.status_code >= 500:
            raise DependencyUnavailableError(f"user-service returned {resp.status_code}")
        if resp.status_code != 200:
            raise DependencyUnavailableError(f"unexpected status {resp.status_code}")

        return resp.json()
```

Punti di progetto:

- **Timeout fisso a 2 s** passato dal costruttore, valore da `config.DEPENDENCY_TIMEOUT`. Mai omesso: una `requests.get` senza `timeout` bloccherebbe il worker indefinitamente e farebbe fallire IT-E08 per timeout del test anziché con un 503.
- **`requests.Timeout` e `requests.ConnectionError` catturati insieme**: i due scenari di IT-E08 (porta chiusa ? `ConnectionError`; host che non risponde ? `Timeout`) devono produrre lo stesso 503.
- **`requests.RequestException` come rete di sicurezza**: qualunque altro errore della libreria diventa 503, non un 500 non gestito. Un 500 non mappato violerebbe il contratto.
- **L'ordine dei controlli conta**: `404` viene valutato *prima* di `>= 500`, così un utente inesistente non viene confuso con un guasto della dipendenza.
- **Il client non conosce il concetto di "organizzatore"**: restituisce il dict utente e lascia al service il controllo sul ruolo. Il nome `OrganizerNotFoundError` è dettato dal mapping del contratto di event-service, ma la semantica del client resta "utente non trovato".
- **Nessun URL hard-coded**: `base_url` arriva da `config.USER_SERVICE_URL` (REQ-EVT-B05 criterio 6).

### 3.2 Mockabilità nei test unitari

Due livelli di isolamento, usati in file diversi:

**a) `responses` — mock a livello HTTP (`test_routes.py`, `test_service.py`).**
Intercetta la chiamata `requests` reale senza sostituire il client. Verifica che URL, metodo e gestione degli status siano corretti:

```python
import responses

@responses.activate
def test_create_event_organizer_not_found(client):
    responses.add(
        responses.GET,
        "http://localhost:5001/api/v1/users/missing-id",
        json={"error": {"code": "NOT_FOUND", "message": "..."}},
        status=404,
    )
    r = client.post("/api/v1/events", json=_payload(organizer_id="missing-id"))
    assert r.status_code == 422
    assert r.json["error"]["code"] == "REFERENCE_NOT_FOUND"
```

Per simulare la dipendenza spenta, `responses` espone il body come eccezione:

```python
responses.add(
    responses.GET,
    "http://localhost:5001/api/v1/users/any-id",
    body=requests.ConnectionError("connection refused"),
)
# -> attesa: 503 DEPENDENCY_UNAVAILABLE
```

**b) Fake client iniettato — mock a livello di interfaccia (`test_service.py`).**
Quando il test riguarda solo la logica di business (es. la tabella delle transizioni), un fake esplicito è più veloce e più leggibile di un mock HTTP:

```python
class FakeUserClient:
    def __init__(self, user=None, exc=None):
        self._user, self._exc = user, exc
    def get_user(self, user_id):
        if self._exc:
            raise self._exc
        return self._user

svc = EventService(MemoryEventRepository(),
                   FakeUserClient(user={"id": "u1", "role": "organizer"}))
```

Il fake è possibile proprio perché `create_app` accetta `user_client` come parametro e `EventService` dipende dall'interfaccia, non dalla classe concreta.

### 3.3 Verifica dell'error mapping nei test

Tabella dei casi che i test unitari devono coprire esplicitamente — corrisponde 1:1 al mapping di `platform-standards.md`:

| Scenario simulato | Atteso | Test acceptance corrispondente |
|---|---|---|
| user-service `200` + `role=organizer` | 201 | IT-E01 |
| user-service `404` | 422 `REFERENCE_NOT_FOUND` | IT-E02 |
| user-service `200` + `role=attendee` | 422 `INVALID_ORGANIZER` | IT-E03 |
| `requests.ConnectionError` | 503 `DEPENDENCY_UNAVAILABLE` | IT-E08 |
| `requests.Timeout` | 503 `DEPENDENCY_UNAVAILABLE` | IT-E08 |
| user-service `500` | 503 `DEPENDENCY_UNAVAILABLE` | IT-E08 |

---

## 4. Persistenza — interfaccia e implementazioni

### 4.1 `repository/base.py`

```python
class AbstractEventRepository(ABC):
    @abstractmethod
    def save(self, event: dict) -> dict: ...
    @abstractmethod
    def find_by_id(self, event_id: str) -> dict | None: ...
    @abstractmethod
    def list_all(self, status: str | None, city: str | None) -> list[dict]: ...
    @abstractmethod
    def update(self, event: dict) -> dict: ...
    @abstractmethod
    def delete(self, event_id: str) -> None: ...
```

Nello stesso modulo vivono le eccezioni di dominio: `EventNotFoundError`, `OrganizerNotFoundError`, `InvalidOrganizerError`, `InvalidStatusTransitionError`, `ValidationError`, `DependencyUnavailableError`.

Nessun `find_by_email`-equivalente: event-service non ha vincoli di unicità su alcun campo.

### 4.2 `memory.py`
Dizionario `{id: event_dict}` in-process. `list_all` filtra iterando. Restituisce sempre copie (`dict(e)`) per evitare mutazioni accidentali dall'esterno.

### 4.3 `json_repo.py`
File `<DATA_DIR>/events.json`, struttura `{"events": [...]}`. Strategia read-all/write-all: ogni operazione carica l'intero file, modifica la lista, riscrive. `os.makedirs(data_dir, exist_ok=True)` nel costruttore.

### 4.4 `sqlite_repo.py`
File `<DATA_DIR>/events.db`. Schema:

```sql
CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    title        TEXT    NOT NULL,
    description  TEXT,
    organizer_id TEXT    NOT NULL,
    venue        TEXT    NOT NULL,
    city         TEXT    NOT NULL,
    start_date   TEXT    NOT NULL,
    end_date     TEXT    NOT NULL,
    capacity     INTEGER NOT NULL,
    price        REAL    NOT NULL,
    status       TEXT    NOT NULL DEFAULT 'draft',
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);
```

`price` è `REAL`: la serializzazione a 2 decimali è responsabilità di `_serialize_event`, non dello schema. Connessione aperta e chiusa per operazione con `try/finally`.

### 4.5 Factory

```python
def _make_repository():
    backend = config.STORAGE_BACKEND
    if backend == "json":
        from app.repository.json_repo import JsonEventRepository
        return JsonEventRepository(config.DATA_DIR)
    if backend == "sqlite":
        from app.repository.sqlite_repo import SqliteEventRepository
        return SqliteEventRepository(config.DATA_DIR)
    from app.repository.memory import MemoryEventRepository
    return MemoryEventRepository()
```

Import lazy, per evitare effetti collaterali al caricamento del modulo nei test.

---

## 5. Riferimento al contratto OpenAPI

Contratto: `contracts/openapi/event-service.yaml` — **non modificabile** (protetto da checksum).

| Schema | Generato da |
|---|---|
| `Event` | `service.py` costruisce il dict, `routes.py::_serialize_event` lo filtra |
| `EventCreate` | `routes.py::_validate_event_input(partial=False)` |
| `EventUpdate` | `routes.py::_validate_event_input(partial=True)` |
| `EventPage` | `routes.py::_paginate` |
| `Error` | `routes.py::_error_response` |
| `Health` | `routes.py::health` |

Vincoli del contratto e dove sono rispettati:

- `additionalProperties: false` ? `_serialize_event` elenca esplicitamente i 12 campi; il dict interno non viene mai serializzato direttamente.
- `format: uuid` su `id` e `organizer_id` ? `uuid.uuid4()` per `id`; `organizer_id` arriva dal client e viene validato per formato.
- `format: date` su `start_date` / `end_date` ? regex `^\d{4}-\d{2}-\d{2}$` in validazione.
- `format: date-time` su `created_at` / `updated_at` ? `%Y-%m-%dT%H:%M:%SZ`.
- `minLength: 3, maxLength: 120` su `title` ? validato in `routes.py`.
- `minimum: 1, maximum: 10000` su `capacity` ? validato in `routes.py`.
- `minimum: 0` su `price` ? validato in `routes.py`.
- `EventStatus` enum ? validato in `routes.py`; le transizioni sono in `service.py`.
- `503` dichiarato su POST/PUT/PATCH ma **non** su GET/DELETE ? coerente col fatto che solo le scritture chiamano user-service (REQ-EVT-E02/E03/E06 lo vietano esplicitamente).
- Header `Location` su 201 ? aggiunto in `create_event`.

---

## 6. Strategia di test

### 6.1 `test_repository.py`
Fixture parametrizzata sui tre backend (`memory`, `json` con `tmp_path`, `sqlite` con `tmp_path`). Stessa suite eseguita 3 volte: save/find/list/filtri/update/delete, eccezioni, creazione automatica di `DATA_DIR`. Nessun mock HTTP: il repository non conosce la rete.

### 6.2 `test_service.py`
`EventService` istanziato con `MemoryEventRepository` e `FakeUserClient`. Nessun Flask, nessuna rete. Copre:
- tabella completa delle transizioni B04, incluse quelle rifiutate e il no-op;
- coerenza date B03, compresi i casi PATCH parziale (solo `start_date`, solo `end_date`);
- distinzione `OrganizerNotFoundError` / `InvalidOrganizerError` (B01 vs B02);
- propagazione di `DependencyUnavailableError` (B05).

### 6.3 `test_routes.py`
Flask test client con `MemoryEventRepository`. Le chiamate a user-service sono mockate con `responses` (mock a livello HTTP), così si verifica anche che il client costruisca l'URL corretto. Copre status code, header `Location`, forma del body, e i sei scenari della tabella §3.3.

### 6.4 `test_contract.py`
Almeno un test per endpoint, ciascuno con `assert_matches_contract("event-service", method, path, response)` da `contracts/validator.py`.

Due accorgimenti già emersi su user-service e da riapplicare qui:
- la workspace root va aggiunta a `sys.path` per importare `contracts.validator`;
- la Flask test response espone `.json` come **proprietà**, mentre il validator si aspetta un `requests.Response` (con `.json()` chiamabile) oppure un dict `{"status_code", "headers", "json"}`. Serve quindi un helper `_adapt(response)` che converta la risposta Flask in quel dict. Il validator è non modificabile: l'adattamento avviene nel test.

Le chiamate a user-service sono mockate con `responses` anche qui, così i test di contratto restano indipendenti dalla rete.

### 6.5 `test_integration.py`
Avvia il **solo** event-service come sottoprocesso su porta libera (`socket.bind(("", 0))`), con `STORAGE_BACKEND=memory`. `USER_SERVICE_URL` viene puntato a una porta chiusa: verifica end-to-end che il processo reale risponda `503 DEPENDENCY_UNAVAILABLE` (equivalente locale di IT-E08). Teardown con `terminate()` + `wait(timeout=5)`.

### 6.6 `test_integration_real.py`
Avvia **due** processi reali — user-service ed event-service — su due porte libere, con `USER_SERVICE_URL` di event-service puntato alla porta effettiva di user-service. Nessun mock. Copre i tre scenari richiesti:

1. organizzatore valido creato via user-service ? `POST /api/v1/events` ? **201**;
2. `organizer_id` inesistente ? **422 `REFERENCE_NOT_FOUND`**;
3. user-service terminato durante il test ? **503 `DEPENDENCY_UNAVAILABLE`**.

Ordine di avvio: prima user-service, poi event-service (che ne riceve l'URL). Ordine di spegnimento inverso. Il terzo scenario va eseguito per ultimo, perché spegne una dipendenza condivisa dal modulo.

### 6.7 Coverage

```bash
# da services/event-service/
pytest tests/ -v --cov=app --cov-report=term-missing
```

Soglia minima **80 %** su `app/`.
