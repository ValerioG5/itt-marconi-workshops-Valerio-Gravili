---
inclusion: always
---

# TechConf — Tech Stack

## Linguaggio e runtime

- **Python 3.12** — unica versione supportata.
- Nessuna dipendenza da runtime esterni (no Docker, no DBMS installato).

## Dipendenze Python

| Pacchetto | Versione minima | Uso |
|---|---|---|
| `flask` | 3.x | Framework HTTP per tutti i microservizi |
| `requests` | 2.x | Chiamate HTTP tra microservizi |
| `pytest` | 8.x | Test runner |
| `pytest-cov` | 5.x | Coverage report (`--cov=app`, soglia ≥ 80 %) |
| `responses` | 0.25.x | Mock delle chiamate HTTP nei test unit |

Ogni servizio mantiene il proprio `requirements.txt` nella sua cartella. Non esiste un virtualenv condiviso tra servizi (evita conflitti di versione se i servizi vengono sviluppati indipendentemente).

## Framework HTTP

**Flask** puro, senza estensioni ORM o serializzatori. Le route seguono il pattern `/api/v1/<risorsa>`. Ogni servizio è un package Python avviato con `python -m app`.

## Persistenza

La persistenza è selezionata a runtime tramite la variabile d'ambiente `STORAGE_BACKEND`:

| Valore | Backend | Note |
|---|---|---|
| `memory` | Dizionario in-process | Default; nessun file; i dati si perdono al riavvio |
| `json` | File JSON su disco | Usa solo `json` dalla stdlib; i file finiscono in `DATA_DIR` |
| `sqlite` | Database SQLite su disco | Usa solo `sqlite3` dalla stdlib; il file finisce in `DATA_DIR` |

**Regola chiave:** il cambio di backend non deve richiedere alcuna modifica alla logica di business. Le regole `REQ-*-B*` non devono sapere quale backend è attivo.

Ogni servizio espone un'interfaccia repository (es. `UserRepository`) con implementazioni separate per i tre backend. La factory che sceglie l'implementazione legge `STORAGE_BACKEND` in un unico punto (tipicamente `app/__init__.py` o `app/config.py`).

```
app/
  repository/
    base.py        # interfaccia / classe base
    memory.py      # implementazione in-memory
    json_repo.py   # implementazione JSON
    sqlite_repo.py # implementazione SQLite
  ...
```

Solo librerie standard per `json` e `sqlite`: **non** installare SQLAlchemy, Peewee, TinyDB o simili.

## Variabili d'ambiente

Tutte le variabili si leggono in un unico modulo di configurazione per servizio (es. `app/config.py`). Mai hard-coded nel codice applicativo.

| Variabile | Descrizione | Default |
|---|---|---|
| `PORT` | Porta su cui il servizio ascolta | 5001–5005 (a seconda del servizio) |
| `USER_SERVICE_URL` | URL base di user-service | `http://localhost:5001` |
| `EVENT_SERVICE_URL` | URL base di event-service | `http://localhost:5002` |
| `REGISTRATION_SERVICE_URL` | URL base di registration-service | `http://localhost:5003` |
| `FEEDBACK_SERVICE_URL` | URL base di feedback-service | `http://localhost:5004` |
| `NOTIFICATION_SERVICE_URL` | URL base di notification-service | `http://localhost:5005` |
| `STORAGE_BACKEND` | Backend di persistenza | `memory` |
| `DATA_DIR` | Directory per file json/sqlite | `./data` |

## Chiamate tra servizi

- Usa `requests` con timeout fisso di **2 secondi**: `requests.get(url, timeout=2)`.
- 404 dal servizio chiamato → 422 `REFERENCE_NOT_FOUND`.
- Timeout, connection error o 5xx → 503 `DEPENDENCY_UNAVAILABLE`.
- Le chiamate sono incapsulate in un client dedicato per ogni dipendenza (es. `app/clients/user_client.py`), mai chiamate inline nelle route.

## Testing

- **Unit test**: `pytest`, dipendenze HTTP mockate con `responses`, repository testato con tutti e tre i backend (usando `tmp_path` di pytest per json/sqlite).
- **Contract test**: almeno 1 test per endpoint che chiama `assert_matches_contract` da `contracts/validator.py`.
- **Integration test (propri)**: per i servizi che chiamano altri, fixture che avvia i servizi reali su porte libere.
- **Coverage**: `pytest --cov=app --cov-report=term-missing`; soglia minima **80 %**.
- Ogni test deve essere riconducibile a un requisito tramite `@pytest.mark.req("REQ-*-B*")` o nome/docstring.

## Avvio

```bash
cd services/<nome>-service
PORT=5001 python -m app
```

La suite di collaudo usa porte **15001–15005** (e 15101+ per resilienza): il servizio legge sempre `PORT` e non assume mai la porta di sviluppo.
