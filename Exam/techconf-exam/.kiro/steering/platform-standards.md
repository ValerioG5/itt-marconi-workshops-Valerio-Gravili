---
inclusion: always
---

# TechConf — Platform Standards

Questo file è la **fonte di verità** per tutte le convenzioni che ogni servizio deve rispettare. Se un requisito di `design.md` o `requirements.md` contraddice questo file, prevale questo file.

---

## Base path e formato

| Tema | Regola |
|---|---|
| Base path | `/api/v1/<risorsa>` |
| Formato | JSON; tutti i campi in `snake_case` |
| Identificativi | `id` UUID v4 generato dal server; **mai** accettato in input dal client |
| Timestamp | ISO 8601 UTC — es. `2026-10-15T09:30:00Z`; ogni risorsa ha `created_at` e `updated_at` (read-only) |
| Date | `YYYY-MM-DD` |
| Importi | Numerici con 2 decimali (`149.00`); valuta implicita EUR |

---

## Paginazione

Tutti gli endpoint di lista accettano i parametri:

```
?page=1&page_size=20
```

- `page` parte da 1; default `1`.
- `page_size` default `20`, massimo `100`.

La risposta ha sempre questa struttura:

```json
{
  "items": [...],
  "page": 1,
  "page_size": 20,
  "total": 57
}
```

---

## Formato degli errori

Ogni risposta di errore (4xx, 5xx) usa **esclusivamente** questa struttura:

```json
{
  "error": {
    "code": "UPPER_SNAKE_CASE",
    "message": "Descrizione leggibile dall'uomo.",
    "details": {}
  }
}
```

- `code`: stringa `UPPER_SNAKE_CASE` (es. `VALIDATION_ERROR`, `NOT_FOUND`, `EMAIL_ALREADY_EXISTS`).
- `message`: testo libero, orientato al debug.
- `details`: oggetto con informazioni aggiuntive (può essere `{}` se non necessario).

---

## Status code

| Codice | Quando usarlo |
|---|---|
| `200` | Lettura o modifica andata a buon fine |
| `201` | Creazione riuscita — risposta include header `Location: /api/v1/<risorsa>/<id>` |
| `204` | Cancellazione riuscita — nessun corpo |
| `400` | JSON malformato nel corpo della richiesta |
| `404` | Risorsa non trovata — codice `NOT_FOUND` |
| `405` | Metodo HTTP non previsto dal contratto |
| `409` | Conflitto — es. `EMAIL_ALREADY_EXISTS`, `ALREADY_REGISTERED`, `EVENT_FULL` |
| `422` | Errore di validazione o regola di business violata — es. `VALIDATION_ERROR`, `REFERENCE_NOT_FOUND`, `INVALID_STATUS_TRANSITION`, `EVENT_NOT_OPEN` |
| `503` | Dipendenza non raggiungibile — codice `DEPENDENCY_UNAVAILABLE` |

---

## Chiamate tra servizi

- Gli URL dei servizi dipendenti si leggono **esclusivamente** da variabili d'ambiente (`USER_SERVICE_URL`, `EVENT_SERVICE_URL`, `REGISTRATION_SERVICE_URL`, `FEEDBACK_SERVICE_URL`, `NOTIFICATION_SERVICE_URL`).
- Default se la variabile non è impostata: `http://localhost:<porta>` (porte di sviluppo 5001–5005).
- **Mai** scrivere URL di altri servizi nel codice sorgente: penalità −5 punti per ogni occorrenza.
- Timeout fisso: **2 secondi** su ogni chiamata (`requests.get(url, timeout=2)`).

**Error mapping obbligatorio:**

| Risposta del servizio chiamato | Risposta da restituire al client |
|---|---|
| `404` | `422` con codice `REFERENCE_NOT_FOUND` |
| Timeout, connessione rifiutata, `5xx` | `503` con codice `DEPENDENCY_UNAVAILABLE` |

---

## Health check

Ogni servizio espone:

```
GET /health
```

Risposta attesa (200):

```json
{
  "status": "ok",
  "service": "<nome-servizio>"
}
```

Il nome servizio è la stringa identificativa del servizio (es. `"user-service"`, `"event-service"`). La suite di collaudo interroga questo endpoint prima di avviare i test e attende che risponda 200.

---

## Persistenza

La persistenza è selezionata a runtime dalla variabile `STORAGE_BACKEND`:

| Valore | Backend | Note |
|---|---|---|
| `memory` | Dizionario in-process | **Default** — nessun file; i dati si perdono al riavvio |
| `json` | File JSON su disco | Solo libreria standard `json`; i file finiscono in `DATA_DIR` |
| `sqlite` | Database SQLite su disco | Solo libreria standard `sqlite3`; il file finisce in `DATA_DIR` |

- `DATA_DIR`: directory per i file json/sqlite; default `./data`; **esclusa da git**.
- **Solo librerie standard** per `json` e `sqlite`: vietato usare SQLAlchemy, Peewee, TinyDB o qualsiasi ORM/ODM.
- Il cambio di backend **non deve richiedere modifiche** alla logica di business (vedere `structure.md` per il pattern repository).

---

## Dipendenze Python

| Pacchetto | Tipo | Scopo |
|---|---|---|
| `flask` | Runtime | Framework HTTP |
| `requests` | Runtime | Chiamate HTTP tra servizi |
| `pytest` | Test | Test runner |
| `pytest-cov` | Test | Coverage report (soglia minima 80 %) |
| `responses` | Test | Mock delle chiamate HTTP nei test unit |

Nessun'altra dipendenza esterna è ammessa senza motivazione esplicita nella spec del servizio.
