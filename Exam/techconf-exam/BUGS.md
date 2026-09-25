# BUGS.md — Registro dei bug

Entrambi i bug sono stati trovati con test propri, non dalla suite di collaudo:
`pytest tests/integration -m mandatory` è risultata verde (27/27) già al primo
giro. La ricerca è stata quindi mirata agli edge case dei campi e alla
compatibilità della libreria standard.

| ID | Issue | Trovato da | Tipo | Requisito | Causa radice | Test di regressione | Commit |
|---|---|---|---|---|---|---|---|
| BUG-01 | #1 | Probe locale su `UserService._now()` con `-W error::DeprecationWarning` | impl | REQ-USR-F01 | `user-service` generava i timestamp con `datetime.utcnow()`, deprecato da Python 3.12 e *scheduled for removal*: alla rimozione il servizio si romperebbe interamente. `event-service` e `registration-service` usavano già `datetime.now(timezone.utc)`, quindi `user-service` era anche l'unico incoerente dei tre | `test_now_does_not_use_deprecated_utcnow`, `test_update_timestamp_does_not_use_deprecated_utcnow`, `test_timestamp_format_is_iso8601_utc` (`services/user-service/tests/test_regression_bug01.py`) | `330fef4` |
| BUG-02 | #2 | Probe locale su POST `/api/v1/users` e `/api/v1/events` con campi di soli spazi | spec | REQ-USR-F02 (criteri 13-16), REQ-EVT-F02 (criteri 16-19) | I criteri vincolavano la lunghezza del valore **grezzo**, che una stringa di soli spazi soddisfa: `first_name = "   "` (len 3) passava il minimo di 1 carattere e l'utente veniva creato con `201`. Stessa lacuna su `title`, `venue` e `city` di event-service. Il requisito diceva "absent or empty" senza definire se il whitespace-only contasse come vuoto — la lacuna era nel requisito, non nel codice | `test_post_user_422_whitespace_first_name`, `test_post_user_422_whitespace_last_name`, `test_post_user_422_whitespace_email`, `test_patch_user_422_whitespace_first_name`, `test_post_user_201_preserves_inner_spaces`, `test_post_event_422_whitespace_title`, `test_post_event_422_whitespace_venue`, `test_post_event_422_whitespace_city`, `test_post_event_201_preserves_inner_spaces` | `d43d4ae` |

---

## BUG-01 — `datetime.utcnow()` deprecato in user-service

**Tipo:** bug di implementazione. La spec era corretta (REQ-USR-F01 criterio 3
chiede un timestamp ISO 8601 UTC, che il codice produceva); sbagliata era l'API
usata per ottenerlo.

**Sintomo.** Eseguendo qualunque creazione o aggiornamento di utente con i
warning promossi a errore, il servizio restituiva `500`:

```
DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for
removal in a future version. Use timezone-aware objects to represent datetimes
in UTC: datetime.datetime.now(datetime.UTC).
  app/service.py:19
```

**Perché non banale.** Il formato prodotto era corretto, quindi nessun test
funzionale e nessun test di contratto lo intercettava: la suite di collaudo
restava verde. Il difetto è di *forward compatibility* — alla rimozione di
`utcnow()` da CPython il servizio cesserebbe di funzionare del tutto, non in
modo parziale. L'incoerenza con gli altri due servizi, che usavano già la forma
timezone-aware, conferma che si trattava di una dimenticanza e non di una scelta.

**Approccio.** Bug di implementazione → fix in Vibe session. Prima il test di
regressione, che promuove `DeprecationWarning` a errore con
`warnings.simplefilter("error", DeprecationWarning)`; verificato che fallisse
sul codice non corretto (2 failed, 1 passed); poi il fix minimo.

**Fix.**
```diff
- from datetime import datetime
+ from datetime import datetime, timezone

- return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
+ return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

**Verifica.** `pytest tests/` su user-service: 71 passed, nessun warning.
`pytest tests/integration -m mandatory`: 27 passed.

---

## BUG-02 — Campi stringa whitespace-only accettati

**Tipo:** bug di specifica. Il codice rispettava alla lettera il requisito; era
il requisito a non coprire il caso.

**Sintomo.**
```
POST /api/v1/users  {"first_name": "   ", "last_name": "   ", "email": "a@b.com"}
-> 201  first_name='   '  last_name='   '

POST /api/v1/events {"title": "   ", "venue": "   ", "city": "   ", ...}
-> 201  title='   '  venue='   '  city='   '
```

**Perché non banale.** Il contratto OpenAPI dichiara `minLength: 1` per
`first_name` e `minLength: 3` per `title`, e una stringa di spazi li soddisfa
formalmente: la risposta era quindi conforme al contratto e nessun test di
`assert_matches_contract` poteva rilevarla. Il risultato è un record
persistito con un nome vuoto a tutti gli effetti pratici, non filtrabile e non
visualizzabile. Da notare che `registration-service` applicava già `.strip()`
su `user_id` ed `event_id`: la piattaforma era internamente incoerente.

**Approccio.** Bug di specifica → **nessuna Vibe session**. Percorso completo
della spec:

1. `spec(user-service,event-service): requirements` — aggiunti REQ-USR-F02
   criteri 13-16 e REQ-EVT-F02 criteri 16-19, con nota sul perché la lacuna
   fosse nel requisito. Commit `ad06904`.
2. `spec(user-service,event-service): design` — documentata la scelta di
   applicare i vincoli di lunghezza al valore *trimmed*, precisando che il
   valore **memorizzato** resta quello inviato dal client: il `.strip()`
   decide se accettare, non riscrive il dato. Commit `32dba9e`.
3. `spec(user-service,event-service): tasks` — aggiunti T-16 (user-service) e
   T-20 (event-service). Commit `1a45027`.
4. Esecuzione dei nuovi task dalla spec. Commit `d43d4ae`.

**Fix.** In `_validate_user_input` e `_validate_event_input`, i controlli di
lunghezza passano da `len(v)` a `len(v.strip())` sui campi stringa obbligatori
(`first_name`, `last_name`, `email` / `title`, `venue`, `city`).

**Nota di progetto.** Il `.strip()` è volutamente confinato alla validazione.
Normalizzare anche il valore persistito avrebbe cambiato silenziosamente
l'input del client, comportamento non richiesto da alcun requisito; i test
`test_post_user_201_preserves_inner_spaces` e
`test_post_event_201_preserves_inner_spaces` bloccano quella regressione.

**Verifica.** user-service 76 passed (coverage 90%), event-service 115 passed
(coverage 92%), `pytest tests/integration -m mandatory` 27 passed.
