# user-service — Design

Servizio: **user-service**
Spec: `.kiro/specs/user-service/`
Contratto: `contracts/openapi/user-service.yaml` ← fonte di verità dell'interfaccia HTTP
Requirements: `.kiro/specs/user-service/requirements.md`

---

## 1. Struttura del package

```
services/user-service/
  app/
    __init__.py          # create_app(): factory Flask + wiring
    __main__.py          # entrypoint: python -m app
    config.py            # lettura env vars (unico punto)
    routes.py            # layer HTTP
    service.py           # layer business logic
    repository/
      __init__.py
      base.py            # AbstractUserRepository
      memory.py          # MemoryUserRepository
      json_repo.py       # JsonUserRepository
      sqlite_repo.py     # SqliteUserRepository
  tests/
    conftest.py
    test_routes.py
    test_service.py
    test_repository.py
    test_contract.py
    test_integration.py
  requirements.txt
```

`user-service` non ha dipendenze da altri servizi TechConf: non ha cartella `clients/`. La cartella `clients/` viene aggiunta solo nei servizi che effettuano chiamate HTTP verso altri servizi (event-service, registration-service, ecc.).

---

## 2. Componenti e responsabilità

### 2.1 `config.py` — configurazione

Unico modulo che legge `os.environ`. Espone costanti importabili dagli altri moduli:

```python
PORT             = int(os.environ.get("PORT", 5001))
STORAGE_BACKEND  = os.environ.get("STORAGE_BACKEND", "memory")
DATA_DIR         = os.environ.get("DATA_DIR", "./data")
```

Nessun altro modulo chiama `os.environ.get` direttamente.

### 2.2 `__init__.py` — factory `create_app()`

Responsabilità:
- Istanzia l'applicazione Flask.
- Legge `STORAGE_BACKEND` da `config` e costruisce il repository concreto (unico punto di decisione del backend).
- Registra le route (`routes.py`) passando il repository alla funzione di setup.
- Non contiene logica di business né accesso diretto al DB.

```python
def create_app(repository=None):
    app = Flask(__name__)
    if repository is None:
        repository = _make_repository()   # legge config.STORAGE_BACKEND
    register_routes(app, repository)
    return app
```

Il parametro `repository` opzionale permette ai test di iniettare un repository finto senza toccare le variabili d'ambiente.

### 2.3 `__main__.py` — entrypoint

```python
from app import create_app
from app.config import PORT

if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
```

Avvio: `python -m app` dalla directory `services/user-service/`. Bind su `0.0.0.0` obbligatorio (la suite di collaudo interroga il servizio dall'esterno come sottoprocesso).

### 2.4 `routes.py` — layer HTTP

Responsabilità **esclusiva**: deserializzare la richiesta HTTP, delegare alla business logic, serializzare la risposta HTTP. Non contiene regole di business.

Funzioni registrate (corrispondono 1:1 agli endpoint del contratto):

| Funzione | Metodo | Path | Descrizione |
|---|---|---|---|
| `health()` | GET | `/health` | REQ-USR-00 |
| `create_user()` | POST | `/api/v1/users` | REQ-USR-E01 |
| `list_users()` | GET | `/api/v1/users` | REQ-USR-E02 |
| `get_user(id)` | GET | `/api/v1/users/<id>` | REQ-USR-E03 |
| `replace_user(id)` | PUT | `/api/v1/users/<id>` | REQ-USR-E04 |
| `update_user(id)` | PATCH | `/api/v1/users/<id>` | REQ-USR-E05 |
| `delete_user(id)` | DELETE | `/api/v1/users/<id>` | REQ-USR-E06 |

**Parsing JSON malformato:** Flask lancia `BadRequest` se il corpo non è JSON valido quando si usa `request.get_json(force=True, silent=False)`. Il gestore di errore globale `@app.errorhandler(400)` intercetta questa eccezione e risponde `400` con `error.code = "MALFORMED_JSON"`.

**Validazione input:** effettuata in `routes.py` prima di chiamare il service. Logica scritta a mano (nessuna libreria di schema). Restituisce `422 VALIDATION_ERROR` per campi mancanti, fuori range, enum non validi, formato email non valido.

**Helper `error_response(code, message, status, details=None)`:** funzione privata in `routes.py` che costruisce il dizionario `{"error": {"code": ..., "message": ..., "details": ...}}` e lo restituisce come risposta Flask. Duplicata per ogni servizio (nessuna libreria condivisa, come da `structure.md`).

**Helper `paginate(items, page, page_size)`:** funzione privata in `routes.py` che restituisce il dizionario `{"items": slice, "page": p, "page_size": ps, "total": n}`. Duplicata per ogni servizio.

### 2.5 `service.py` — layer business logic

Responsabilità: implementare le regole `REQ-USR-B*` e orchestrare le operazioni sul repository. Non conosce Flask, non conosce HTTP, non sa quale backend è attivo.

Riceve il repository come dipendenza iniettata (non lo importa direttamente). Questo permette ai test di `test_service.py` di passare un repository mock senza avviare Flask.

Metodi principali:

| Metodo | Requisiti implementati |
|---|---|
| `create_user(data) -> dict` | REQ-USR-B01, REQ-USR-B02, REQ-USR-F01 |
| `list_users(filters, page, page_size) -> (list, int)` | REQ-USR-B03, REQ-USR-E02 |
| `get_user(id) -> dict` | REQ-USR-E03 |
| `replace_user(id, data) -> dict` | REQ-USR-B01, REQ-USR-B02, REQ-USR-E04 |
| `update_user(id, data) -> dict` | REQ-USR-B01, REQ-USR-B02, REQ-USR-E05 |
| `delete_user(id) -> None` | REQ-USR-E06 |

Regole di business implementate in `service.py`:
- **REQ-USR-B01**: prima di creare o aggiornare, interroga il repository per verificare che nessun altro utente possieda la stessa email (confronto case-insensitive sul valore già normalizzato).
- **REQ-USR-B02**: `email = data["email"].lower()` applicato all'ingresso di ogni operazione di scrittura, prima di qualsiasi confronto o persistenza.
- **REQ-USR-F01** (generazione id e timestamps): `id = str(uuid.uuid4())`, `now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")`.

Eccezioni sollevate da `service.py` (catturate in `routes.py`):

| Eccezione | Causa | HTTP |
|---|---|---|
| `EmailAlreadyExistsError` | email duplicata | 409 |
| `UserNotFoundError` | id inesistente | 404 |

---

## 3. Persistenza — interfaccia e implementazioni

### 3.1 `repository/base.py` — `AbstractUserRepository`

Interfaccia che `service.py` usa come unico punto di accoppiamento alla persistenza. Le implementazioni concrete non sono mai importate da `service.py`.

```python
from abc import ABC, abstractmethod

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
```

### 3.2 `repository/memory.py` — `MemoryUserRepository`

Storage: dizionario Python `{id: user_dict}` in-process. Dati persi al riavvio.

```
_store: dict[str, dict]  # chiave = user id
```

`find_by_email` itera `_store.values()` confrontando `u["email"] == email` (entrambi già in minuscolo). `list_all` filtra in-memory. Tutte le operazioni sono O(n) — accettabile per un esame.

### 3.3 `repository/json_repo.py` — `JsonUserRepository`

Storage: file `<DATA_DIR>/users.json`. Struttura del file:

```json
{"users": [{"id": "...", "first_name": "...", ...}, ...]}
```

Strategia di accesso: **read-all / write-all**. Ogni operazione:
1. Apre il file, deserializza con `json.load`.
2. Modifica la lista in memoria.
3. Riscrive l'intero file con `json.dump`.

Questo approccio è semplice e corretto per il carico di un esame. Il file viene creato vuoto (`{"users": []}`) se non esiste. `DATA_DIR` viene creato con `os.makedirs(DATA_DIR, exist_ok=True)` all'inizializzazione del repository.

### 3.4 `repository/sqlite_repo.py` — `SqliteUserRepository`

Storage: file `<DATA_DIR>/users.db`. Schema:

```sql
CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    first_name  TEXT NOT NULL,
    last_name   TEXT NOT NULL,
    email       TEXT NOT NULL UNIQUE,
    company     TEXT,
    role        TEXT NOT NULL DEFAULT 'attendee',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
```

Usa solo `sqlite3` dalla stdlib. Connessione aperta e chiusa per ogni operazione (strategia semplice, nessun connection pool). `DATA_DIR` viene creato con `os.makedirs` all'inizializzazione. `find_by_email` usa `WHERE email = ?` (già normalizzata). `list_all` costruisce la query dinamicamente aggiungendo clausole `WHERE` in base ai filtri presenti.

### 3.5 Factory in `__init__.py`

```python
def _make_repository():
    backend = config.STORAGE_BACKEND
    if backend == "json":
        from app.repository.json_repo import JsonUserRepository
        return JsonUserRepository(config.DATA_DIR)
    if backend == "sqlite":
        from app.repository.sqlite_repo import SqliteUserRepository
        return SqliteUserRepository(config.DATA_DIR)
    # default: memory
    from app.repository.memory import MemoryUserRepository
    return MemoryUserRepository()
```

Gli import sono intenzionalmente lazy (dentro la funzione) per evitare effetti collaterali al caricamento del modulo durante i test.

---

## 4. Riferimento al contratto OpenAPI

Contratto: `contracts/openapi/user-service.yaml` — **non modificabile** (protetto da checksum).

Mapping schema → componente responsabile:

| Schema contratto | Generato da |
|---|---|
| `User` | `service.py` (costruisce il dict) + `routes.py` (lo serializza come JSON) |
| `UserCreate` | `routes.py` (validazione input) |
| `UserUpdate` | `routes.py` (validazione input parziale per PATCH) |
| `UserPage` | `routes.py` (helper `paginate`) |
| `Error` | `routes.py` (helper `error_response`) |
| `Health` | `routes.py` (endpoint `/health`) |

Vincoli del contratto rispettati nell'implementazione:
- `additionalProperties: false` → `routes.py` serializza **solo** i campi elencati in `User`, mai l'intero dizionario interno raw.
- `format: uuid` per `id` → `uuid.uuid4()` in `service.py`.
- `format: date-time` per `created_at`, `updated_at` → formato `YYYY-MM-DDTHH:MM:SSZ` in `service.py`.
- `format: email` per `email` → validazione regex minimale in `routes.py` (presenza `@` e dominio).
- `Role` enum `[attendee, speaker, organizer]` → validato in `routes.py`.
- Header `Location` su 201 → `routes.py` aggiunge `Location: /api/v1/users/<id>` nella risposta.

---

## 5. Strategia di test

### 5.1 `tests/test_routes.py` — test unit del layer HTTP

- Usa il Flask test client (`app.test_client()`).
- Il repository è un mock (oggetto con i metodi di `AbstractUserRepository` sostituiti da `MagicMock` o da una implementazione `MemoryUserRepository` fresca).
- Le chiamate HTTP verso altri servizi non esistono in `user-service`: nessun mock con `responses` necessario in questo servizio.
- Copre: status code corretti, header `Location`, struttura del body, gestione 400/404/409/422.
- Ogni test porta il marker `@pytest.mark.req("REQ-USR-Exx")`.

### 5.2 `tests/test_service.py` — test unit della business logic

- Istanzia `UserService` con un `MemoryUserRepository` fresco.
- Non avvia Flask.
- Copre le regole `REQ-USR-B01`, `REQ-USR-B02`, `REQ-USR-B03` in isolamento.
- Verifica che `EmailAlreadyExistsError` venga sollevato nei casi corretti.
- Ogni test porta il marker `@pytest.mark.req("REQ-USR-Bxx")`.

### 5.3 `tests/test_repository.py` — test unit dei tre backend

- Stessa suite di test parametrizzata su tre fixture: `MemoryUserRepository`, `JsonUserRepository(tmp_path)`, `SqliteUserRepository(tmp_path)`.
- Usa `tmp_path` di pytest per file temporanei (isolamento automatico tra test).
- Verifica: save/find/update/delete su tutti e tre i backend, unicità email in SQLite (vincolo UNIQUE), creazione automatica di `DATA_DIR`.

### 5.4 `tests/test_contract.py` — test di conformità al contratto

- Usa il Flask test client con `MemoryUserRepository`.
- Per ogni endpoint chiama `assert_matches_contract("user-service", method, path, response)` da `contracts/validator.py`.
- Almeno un test per endpoint (7 endpoint + health = 8 test minimi).
- Verifica sia le risposte di successo sia le risposte di errore.

### 5.5 `tests/test_integration.py` — test di integrazione con servizio reale

- Fixture `live_server` (scope `module`):
  1. Trova una porta libera via `socket.bind(("", 0))`.
  2. Lancia `subprocess.Popen(["python", "-m", "app"], cwd="services/user-service", env={..., "PORT": str(port), "STORAGE_BACKEND": "memory"})`.
  3. Polling su `GET /health` con timeout 10 s.
  4. `yield base_url`.
  5. Teardown: `proc.terminate(); proc.wait()`.
- Copre almeno: 1 caso positivo (POST → 201), 1 caso 404, 1 caso 409 (email duplicata).
- Verifica che il processo reale rispetti il contratto end-to-end, senza mock.

### 5.6 Coverage e comando

```bash
# dalla directory services/user-service/
pytest tests/ -v --cov=app --cov-report=term-missing
```

Soglia minima: **80 %** su `app/`. Il modulo `app/config.py` è quasi interamente coperto dall'import automatico; i branch non coperti (backend non usati) sono accettabili sopra l'80 %.
