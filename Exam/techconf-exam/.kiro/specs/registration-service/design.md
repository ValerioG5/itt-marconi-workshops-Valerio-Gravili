# registration-service — Design

Servizio: **registration-service**
Contratto: `contracts/openapi/registration-service.yaml` ← fonte di verità dell'interfaccia HTTP
Requirements: `.kiro/specs/registration-service/requirements.md`
Dipendenze runtime: **user-service** e **event-service** via HTTP

---

## 1. Struttura del package

```
services/registration-service/
  app/
    __init__.py              # create_app(): factory Flask + wiring
    __main__.py              # entrypoint: python -m app
    config.py                # lettura env vars (unico punto)
    routes.py                # layer HTTP
    service.py               # business logic REQ-REG-B*
    clients/
      __init__.py
      base_client.py         # timeout + error mapping condivisi
      user_client.py         # GET /api/v1/users/{id}
      event_client.py        # GET /api/v1/events/{id}
    repository/
      __init__.py
      base.py                # AbstractRegistrationRepository + eccezioni
      memory.py
      json_repo.py
      sqlite_repo.py
  tests/
    conftest.py
    test_repository.py
    test_clients.py
    test_service.py
    test_routes.py
    test_contract.py
    test_integration.py      # solo registration-service, dipendenze spente
    test_integration_real.py # i tre servizi reali, scenario capienza
  requirements.txt
```

**Novità rispetto a event-service: `clients/base_client.py`.** `structure.md` prevede esplicitamente questa eccezione per i servizi con più di una dipendenza HTTP. registration-service chiama due servizi, e la logica di error mapping (404 → `REFERENCE_NOT_FOUND`, timeout/connessione/5xx → `DEPENDENCY_UNAVAILABLE`) è identica per entrambi. Duplicarla in due file esporrebbe al rischio di drift: una correzione applicata a un solo client farebbe fallire silenziosamente IT-R10. La classe base vive solo dentro questo package e non è condivisa con altri servizi.

---

## 2. Componenti e responsabilità

### 2.1 `config.py`

```python
PORT               = int(os.environ.get("PORT", 5003))
USER_SERVICE_URL   = os.environ.get("USER_SERVICE_URL",  "http://localhost:5001")
EVENT_SERVICE_URL  = os.environ.get("EVENT_SERVICE_URL", "http://localhost:5002")
STORAGE_BACKEND    = os.environ.get("STORAGE_BACKEND", "memory")
DATA_DIR           = os.environ.get("DATA_DIR", "./data")
DEPENDENCY_TIMEOUT = 2
```

### 2.2 `__init__.py` — factory

```python
def create_app(repository=None, user_client=None, event_client=None):
    app = Flask(__name__)
    if repository is None:
        repository = _make_repository()
    if user_client is None:
        user_client = UserClient(config.USER_SERVICE_URL, config.DEPENDENCY_TIMEOUT)
    if event_client is None:
        event_client = EventClient(config.EVENT_SERVICE_URL, config.DEPENDENCY_TIMEOUT)
    service = RegistrationService(repository, user_client, event_client)
    register_routes(app, service)
    return app
```

Tre parametri iniettabili: i test sostituiscono i due client con fake espliciti.

### 2.3 `routes.py` — layer HTTP

| Funzione | Metodo | Path | Requisito |
|---|---|---|---|
| `health()` | GET | `/health` | REQ-REG-00 |
| `create_registration()` | POST | `/api/v1/registrations` | REQ-REG-E01 |
| `list_registrations()` | GET | `/api/v1/registrations` | REQ-REG-E02 |
| `registration_stats()` | GET | `/api/v1/registrations/stats` | REQ-REG-B08 |
| `get_registration(id)` | GET | `/api/v1/registrations/<id>` | REQ-REG-E03 |
| `update_registration(id)` | PATCH | `/api/v1/registrations/<id>` | REQ-REG-E04 |
| `delete_registration(id)` | DELETE | `/api/v1/registrations/<id>` | REQ-REG-E05 |

**Ordine di registrazione delle route — vincolo non negoziabile.** `/api/v1/registrations/stats` deve essere registrata **prima** di `/api/v1/registrations/<registration_id>`. Werkzeug preferisce le regole statiche a quelle con convertitore, ma l'ordine esplicito rende l'intenzione evidente e protegge da una regressione se il path dovesse cambiare. Senza questa attenzione, `GET /stats` verrebbe risolto come "registrazione con id `stats`" e IT-R08 riceverebbe un `404` al posto delle statistiche.

**REQ-REG-E06 — PUT deve dare 405.** La route `/api/v1/registrations/<id>` viene registrata con `methods=["GET", "PATCH", "DELETE"]`. Werkzeug risponde quindi `405` automaticamente per il `PUT`, ma il corpo di default è HTML. Il contratto pretende il corpo `Error`, per cui serve un handler dedicato:

```python
@app.errorhandler(405)
def handle_method_not_allowed(e):
    return _error_response("METHOD_NOT_ALLOWED", "Method not allowed for this resource.", 405)
```

### 2.4 `service.py` — business logic

| Metodo | Requisiti |
|---|---|
| `create_registration(data)` | B01, B02, B03, B04, B05, B06, F01, E01 |
| `list_registrations(user_id, event_id, status, page, page_size)` | E02 |
| `get_registration(id)` | E03 |
| `update_status(id, status)` | B07, E04 |
| `delete_registration(id)` | E05 |
| `get_stats(event_id)` | B08 |

---

## 3. Calcolo della capienza e consistenza della scrittura

Questa è la parte più delicata del servizio: da essa dipendono IT-R05, IT-R06, IT-R07 e IT-J01.

### 3.1 Come si calcola la capienza disponibile

Tre grandezze, con tre origini diverse:

| Grandezza | Origine | Note |
|---|---|---|
| `capacity` | event-service, campo `capacity` della risposta `GET /api/v1/events/{id}` | mai dal payload del client |
| `confirmed` | repository locale, conteggio delle registrazioni con `event_id` dato **e** `status == "confirmed"` | mai calcolato da event-service |
| `available` | `max(0, capacity - confirmed)` | il clamp evita valori negativi se `capacity` viene ridotta a posteriori |

Il conteggio è un'operazione di prima classe dell'interfaccia del repository:

```python
@abstractmethod
def count_confirmed(self, event_id: str) -> int:
    """Numero di registrazioni 'confirmed' per l'evento."""
```

Il motivo è duplice. Primo, il filtro "solo confirmed" è esattamente il punto in cui un bug produrrebbe IT-R06 o IT-R07 rotti: conteggiare anche le `cancelled` renderebbe l'evento pieno per sempre. Tenerlo in un solo metodo, testato su tutti e tre i backend, lo rende verificabile una volta sola. Secondo, permette a SQLite di usare `SELECT COUNT(*) ... WHERE event_id = ? AND status = 'confirmed'` invece di caricare e filtrare in Python.

Il clamp a `0` in `available` (REQ-REG-B08 criterio 4) serve a un caso reale: se un organizzatore riduce `capacity` dopo che le iscrizioni sono già state accettate, `capacity - confirmed` diventerebbe negativo e violerebbe l'aspettativa del client.

### 3.2 Consistenza tra verifica e scrittura

Il rischio è la classica finestra check-then-act: fra il momento in cui si conta l'occupazione e il momento in cui si scrive la nuova registrazione, lo stato potrebbe cambiare e far superare la capienza.

**Ordine delle operazioni in `create_registration`:**

```
1. validazione dei campi                    (in routes.py, nessuna I/O)
2. user_client.get_user(user_id)            -> I/O di rete
3. event_client.get_event(event_id)         -> I/O di rete
4. controllo event["status"] == "published"  (in memoria)
5. repository.find_confirmed(user_id, event_id)  -> duplicato?     ┐
6. repository.count_confirmed(event_id)          -> capienza       │ sezione
7. repository.save(registration)                                  ┘ critica
```

Il principio di progetto è: **tutte le chiamate di rete stanno prima del passo 5**. I passi 5–7 toccano solo il repository locale e non contengono alcuna I/O verso altri servizi. La finestra fra il conteggio e la scrittura si riduce così a poche istruzioni Python, senza attese di rete in mezzo — che sono l'unico punto in cui, in un server a thread, il controllo passerebbe a un'altra richiesta per un tempo apprezzabile. REQ-REG-B05 criterio 6 codifica esattamente questo vincolo.

**Perché questo basta in single-thread.** Flask in modalità di sviluppo serve una richiesta per volta: i passi 5–7 non possono essere interrotti da un'altra registrazione, quindi la sequenza conta-e-scrivi è di fatto atomica. La suite di collaudo avvia i servizi come processi singoli, e questo è lo scenario che deve risultare corretto.

**Cosa succede se il server diventa multi-thread.** L'ordinamento descritto non è di per sé una garanzia di mutua esclusione. Per questo la sezione critica è protetta anche da un lock di processo:

```python
class RegistrationService:
    def __init__(self, repository, user_client, event_client):
        self.repository = repository
        self.user_client = user_client
        self.event_client = event_client
        self._seat_lock = threading.Lock()      # serializza duplicato+capienza+scrittura

    def create_registration(self, data):
        # ... passi 1-4: validazioni e chiamate di rete, FUORI dal lock
        user_id, event_id = data["user_id"], data["event_id"]
        self.user_client.get_user(user_id)
        event = self.event_client.get_event(event_id)
        if event["status"] != "published":
            raise EventNotOpenError(event_id)

        # passi 5-7: sezione critica, nessuna I/O di rete all'interno
        with self._seat_lock:
            if self.repository.find_confirmed(user_id, event_id) is not None:
                raise AlreadyRegisteredError(user_id, event_id)
            if self.repository.count_confirmed(event_id) >= event["capacity"]:
                raise EventFullError(event_id)
            return self.repository.save(self._build(user_id, event_id, event["price"]))
```

Il lock è deliberatamente **fuori** dalle chiamate di rete: tenerlo durante una `requests.get` con timeout 2 s serializzerebbe l'intero servizio sulla latenza della dipendenza. Racchiude solo le operazioni locali, quindi il costo in contesa è trascurabile.

Il lock risolve la concorrenza fra thread dello stesso processo, non fra processi distinti che condividono un backend `json` o `sqlite`. Questo limite è accettato consapevolmente: la piattaforma avvia una sola istanza per servizio, e introdurre un lock inter-processo (file di lock, transazioni `BEGIN IMMEDIATE`) aggiungerebbe complessità non richiesta dalla traccia. Su SQLite, il vincolo di unicità descritto in §5.4 fornisce comunque una rete di sicurezza a livello di storage per il caso del duplicato.

### 3.3 Cancellazione che libera il posto

REQ-REG-B07 criterio 3 non richiede codice dedicato: poiché `count_confirmed` filtra per `status == "confirmed"`, portare una registrazione a `cancelled` la esclude automaticamente dal conteggio. Il posto si libera come conseguenza del modo in cui l'occupazione è calcolata, non per effetto di un contatore mantenuto a mano.

Questa è una scelta precisa. Un contatore persistito (`event_occupancy`) andrebbe aggiornato in ogni punto che modifica lo stato — creazione, patch, delete — e ogni punto dimenticato sarebbe un bug di capienza. Derivare il conteggio dai dati rende impossibile quella classe di errori, al prezzo di una scansione per ogni verifica: costo irrilevante alla scala dell'esame.

Ne segue che anche `DELETE` (REQ-REG-E05 criterio 3) libera un posto senza logica aggiuntiva: il record non esiste più, quindi non viene contato.

---

## 4. Isolamento delle chiamate HTTP

### 4.1 `clients/base_client.py`

Unico modulo del servizio che importa `requests`.

```python
import requests
from app.repository.base import DependencyUnavailableError, ReferenceNotFoundError


class BaseHttpClient:
    """Timeout ed error mapping condivisi dai client del servizio.

    Mapping (platform-standards.md):
        404              -> ReferenceNotFoundError    => 422 REFERENCE_NOT_FOUND
        timeout          -> DependencyUnavailableError => 503
        connection error -> DependencyUnavailableError => 503
        5xx              -> DependencyUnavailableError => 503
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

        if resp.status_code == 404:
            raise ReferenceNotFoundError(resource_id)
        if resp.status_code >= 500:
            raise DependencyUnavailableError(f"{url} returned {resp.status_code}")
        if resp.status_code != 200:
            raise DependencyUnavailableError(f"{url} returned {resp.status_code}")
        return resp.json()
```

`UserClient` ed `EventClient` sono sottili specializzazioni:

```python
class UserClient(BaseHttpClient):
    def get_user(self, user_id): return self._get("/api/v1/users", user_id)

class EventClient(BaseHttpClient):
    def get_event(self, event_id): return self._get("/api/v1/events", event_id)
```

Entrambe le dipendenze producono `ReferenceNotFoundError` sul 404, coerentemente con REQ-REG-B01 criterio 2 e REQ-REG-B02 criterio 2, che chiedono lo stesso `REFERENCE_NOT_FOUND` per utente ed evento mancanti. Non serve distinguerle.

### 4.2 Mockabilità nei test

Come per event-service, due livelli:

- **`responses`** in `test_clients.py`, `test_routes.py` e `test_contract.py`: intercetta la rete e verifica URL, timeout e mapping degli status.
- **Fake iniettati** in `test_service.py`: `FakeUserClient` e `FakeEventClient` che restituiscono dati o sollevano eccezioni a comando, e contano le chiamate. Indispensabili per i test sulla capienza, dove servono molte registrazioni consecutive senza rumore di rete.

```python
class FakeEventClient:
    def __init__(self, event=None, exc=None):
        self.event, self.exc, self.calls = event, exc, 0
    def get_event(self, event_id):
        self.calls += 1
        if self.exc:
            raise self.exc
        return self.event
```

### 4.3 Mapping eccezione → HTTP

| Eccezione | HTTP | `error.code` |
|---|---|---|
| `RegistrationNotFoundError` | 404 | `NOT_FOUND` |
| `EventNotFoundForStatsError` | 404 | `NOT_FOUND` |
| `ReferenceNotFoundError` | 422 | `REFERENCE_NOT_FOUND` |
| `EventNotOpenError` | 422 | `EVENT_NOT_OPEN` |
| `InvalidStatusTransitionError` | 422 | `INVALID_STATUS_TRANSITION` |
| `ValidationError` | 422 | `VALIDATION_ERROR` |
| `AlreadyRegisteredError` | 409 | `ALREADY_REGISTERED` |
| `EventFullError` | 409 | `EVENT_FULL` |
| `DependencyUnavailableError` | 503 | `DEPENDENCY_UNAVAILABLE` |

Nota sull'ordine di cattura: `AlreadyRegisteredError` e `EventFullError` mappano entrambe su 409 ma con codici distinti, quindi vanno intercettate separatamente.

---

## 5. Persistenza

### 5.1 `repository/base.py`

```python
class AbstractRegistrationRepository(ABC):
    @abstractmethod
    def save(self, registration: dict) -> dict: ...
    @abstractmethod
    def find_by_id(self, registration_id: str) -> dict | None: ...
    @abstractmethod
    def find_confirmed(self, user_id: str, event_id: str) -> dict | None: ...
    @abstractmethod
    def count_confirmed(self, event_id: str) -> int: ...
    @abstractmethod
    def list_all(self, user_id, event_id, status) -> list[dict]: ...
    @abstractmethod
    def update(self, registration: dict) -> dict: ...
    @abstractmethod
    def delete(self, registration_id: str) -> None: ...
```

Due metodi in più rispetto agli altri servizi: `find_confirmed` (REQ-REG-B04) e `count_confirmed` (REQ-REG-B05, REQ-REG-P01 criterio 6). Sono le due query che implementano le regole di capienza, ed esistono come operazioni nominate proprio perché quelle regole sono il cuore del servizio.

### 5.2 `memory.py`
Dizionario `{id: registration}`. `find_confirmed` e `count_confirmed` iterano filtrando su `status == "confirmed"`.

### 5.3 `json_repo.py`
File `<DATA_DIR>/registrations.json`, struttura `{"registrations": [...]}`, read-all/write-all.

### 5.4 `sqlite_repo.py`
File `<DATA_DIR>/registrations.db`. Schema:

```sql
CREATE TABLE IF NOT EXISTS registrations (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL,
    event_id   TEXT NOT NULL,
    amount     REAL NOT NULL,
    status     TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_registrations_event_status
    ON registrations (event_id, status);
```

L'indice su `(event_id, status)` è la coppia esatta interrogata da `count_confirmed` e `find_confirmed`, cioè le due query nel percorso critico di ogni creazione.

`count_confirmed` sfrutta il database invece di filtrare in Python:

```sql
SELECT COUNT(*) FROM registrations WHERE event_id = ? AND status = 'confirmed'
```

**Nessun vincolo `UNIQUE` sulla coppia `(user_id, event_id)`**: sarebbe sbagliato. REQ-REG-B04 criterio 2 permette a un utente di iscriversi di nuovo dopo aver cancellato, e in quel momento esistono legittimamente due righe con la stessa coppia (una `cancelled`, una `confirmed`). Un indice unico su `(user_id, event_id)` romperebbe IT-R07. Il vincolo corretto sarebbe un indice unico parziale limitato alle righe `confirmed`; è disponibile in SQLite come `CREATE UNIQUE INDEX ... WHERE status = 'confirmed'` e viene creato come rete di sicurezza a livello di storage:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_registrations_confirmed
    ON registrations (user_id, event_id) WHERE status = 'confirmed';
```

La regola di business resta comunque in `service.py`: l'indice è una difesa in profondità, non la sede del requisito.

---

## 6. Riferimento al contratto OpenAPI

Contratto: `contracts/openapi/registration-service.yaml` — **non modificabile**.

| Schema | Generato da |
|---|---|
| `Registration` | `service.py` costruisce, `routes.py::_serialize_registration` filtra |
| `RegistrationCreate` | `routes.py::_validate_create_input` |
| `RegistrationPatch` | `routes.py::_validate_patch_input` |
| `RegistrationPage` | `routes.py::_paginate` |
| `RegistrationStats` | `routes.py::registration_stats` |
| `Error` | `routes.py::_error_response` |
| `Health` | `routes.py::health` |

Vincoli rilevanti:
- `Registration` richiede esattamente 7 campi, `additionalProperties: false` → `_serialize_registration` li elenca.
- `RegistrationCreate` ammette **solo** `user_id` e `event_id`: `amount` e `status` non sono accettabili in input (REQ-REG-F02 criteri 4-5).
- `RegistrationPatch` ha `status` fra i `required` → un PATCH senza `status` è `422` (REQ-REG-B07 criterio 6).
- `RegistrationStats` richiede i 4 campi `event_id`, `capacity`, `confirmed`, `available`, tutti interi tranne `event_id`.
- `PUT` dichiara solo la risposta `405`, con corpo `Error`.
- `503` è dichiarato su `POST` e su `GET /stats`, ma non su `GET` lista, `GET` singolo, `PATCH`, `DELETE`: coerente col fatto che solo creazione e statistiche chiamano dipendenze.
- `amount` è `type: number` → serializzato come float a 2 decimali.

---

## 7. Strategia di test

### 7.1 `test_repository.py`
Fixture parametrizzata sui tre backend. Oltre al CRUD, copre in modo esplicito:
- `count_confirmed` con mix di `confirmed` e `cancelled` — deve contare solo le prime;
- `count_confirmed` dopo una cancellazione — deve diminuire;
- `find_confirmed` che ignora le `cancelled`;
- isolamento fra `event_id` diversi.

### 7.2 `test_clients.py`
`responses`. Verifica il mapping per entrambi i client: 200, 404 → `ReferenceNotFoundError`, 500 → `DependencyUnavailableError`, `ConnectionError`, `Timeout`, e la forma dell'URL costruito a partire dalla base URL configurata.

### 7.3 `test_service.py`
`MemoryRegistrationRepository` più fake client. È il file che copre le regole di capienza in isolamento:
- creazione con `amount` copiato dal prezzo dell'evento;
- `amount` nel payload ignorato;
- doppia iscrizione `confirmed` → `AlreadyRegisteredError`;
- nuova iscrizione dopo cancellazione → ammessa;
- capienza raggiunta → `EventFullError`;
- cancellazione che libera il posto e permette una nuova iscrizione;
- `confirmed → cancelled` ammessa, `cancelled → confirmed` rifiutata, no-op ammesso;
- evento non pubblicato → `EventNotOpenError` per `draft` e `cancelled`;
- `stats` con `available` clampato a 0;
- PATCH che non chiama alcuna dipendenza (asserzione sui contatori dei fake).

### 7.4 `test_routes.py`
Test client Flask, dipendenze mockate con `responses`. Include i casi che riguardano il routing:
- `GET /api/v1/registrations/stats` risolto come statistiche e non come `id`;
- `PUT` → `405` con corpo conforme a `Error`;
- ordine dei controlli: payload invalido → `422` senza alcuna chiamata di rete.

### 7.5 `test_contract.py`
Un test per endpoint con `assert_matches_contract("registration-service", ...)`. Stessi due accorgimenti già usati negli altri servizi: workspace root in `sys.path` e helper `_adapt` che converte la risposta Flask nel dict atteso dal validator, che non è modificabile.

### 7.6 `test_integration.py`
Solo registration-service come sottoprocesso, con `USER_SERVICE_URL` ed `EVENT_SERVICE_URL` su porte chiuse: verifica `503` end-to-end (equivalente locale di IT-R10) e che health, `404` e `422` di validazione restino raggiungibili senza dipendenze.

### 7.7 `test_integration_real.py`
Avvia **tre** processi reali — user-service, event-service, registration-service — e riproduce lo scenario limite della capienza senza alcun mock:

1. crea un organizzatore e un evento con `capacity=2`, poi lo pubblica;
2. registra due utenti → entrambi `201`;
3. registra un terzo utente → **`409 EVENT_FULL`**;
4. cancella una delle due registrazioni via `PATCH` → `200`;
5. registra un quarto utente → **`201`**, perché il posto si è liberato;
6. verifica `stats` coerente lungo tutto il percorso.

Ordine di avvio: user → event → registration, ciascuno con gli URL dei precedenti. Spegnimento in ordine inverso.

### 7.8 Coverage

```bash
# da services/registration-service/
pytest tests/ -v --cov=app --cov-report=term-missing
```

Soglia minima **80 %** su `app/`.
