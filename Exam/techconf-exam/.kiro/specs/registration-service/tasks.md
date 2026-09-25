# registration-service — Tasks

Servizio: **registration-service**
Ordine: sequenziale. Commit per task: `feat(registration-service): <descrizione> [T-XX]`

---

- [ ] **T-01 — Scaffolding del package e configurazione**

  - `app/config.py` — `PORT` (5003), `USER_SERVICE_URL` (`http://localhost:5001`), `EVENT_SERVICE_URL` (`http://localhost:5002`), `STORAGE_BACKEND` (`memory`), `DATA_DIR` (`./data`), `DEPENDENCY_TIMEOUT = 2`
  - `app/repository/base.py` — `AbstractRegistrationRepository` con 7 metodi astratti (`save`, `find_by_id`, `find_confirmed`, `count_confirmed`, `list_all`, `update`, `delete`) e le eccezioni `RegistrationNotFoundError`, `EventNotFoundForStatsError`, `ReferenceNotFoundError`, `EventNotOpenError`, `AlreadyRegisteredError`, `EventFullError`, `InvalidStatusTransitionError`, `ValidationError`, `DependencyUnavailableError`
  - `app/repository/{memory,json_repo,sqlite_repo}.py` — stub `NotImplementedError`
  - `app/clients/{__init__,base_client,user_client,event_client}.py` — stub
  - `app/service.py` — stub `RegistrationService(repository, user_client, event_client)`
  - `app/routes.py` — stub `register_routes(app, service)`
  - `app/__init__.py` — `create_app(repository=None, user_client=None, event_client=None)` + `_make_repository()` lazy
  - `app/__main__.py` — entrypoint bind `0.0.0.0`
  - `tests/__init__.py`, `tests/conftest.py` (marker `req`)
  - `requirements.txt` — `flask`, `requests`, `pytest`, `pytest-cov`, `responses`, `pyyaml`, `jsonschema`

  _Requirements: REQ-REG-P02_

---

- [ ] **T-02 — Health endpoint e handler 400/405**

  - `_error_response(code, message, status, details=None)` in `routes.py`.
  - `GET /health` → `{"status": "ok", "service": "registration-service"}`.
  - `@app.errorhandler(400)` → `MALFORMED_JSON`.
  - `@app.errorhandler(405)` → `METHOD_NOT_ALLOWED` con corpo conforme allo schema `Error`. Necessario perché il contratto dichiara la risposta `405` per `PUT` e il default HTML di Werkzeug non la rispetta.

  _Requirements: REQ-REG-00, REQ-REG-F02 criterio 1, REQ-REG-E06, REQ-REG-C01_

---

- [ ] **T-03 — Repository memory**

  Implementa `MemoryRegistrationRepository`. Oltre al CRUD:
  - `find_confirmed(user_id, event_id)` → prima registrazione con quella coppia **e** `status == "confirmed"`, altrimenti `None`.
  - `count_confirmed(event_id)` → numero di registrazioni con quell'`event_id` **e** `status == "confirmed"`.
  - `list_all(user_id, event_id, status)` → filtri AND, tutti opzionali.

  _Requirements: REQ-REG-P01 criteri 1, 6, REQ-REG-B04, REQ-REG-B05_

---

- [ ] **T-04 — Repository JSON**

  `JsonRegistrationRepository` su `<DATA_DIR>/registrations.json`, struttura `{"registrations": [...]}`, read-all/write-all, `os.makedirs(..., exist_ok=True)`. Tutti e 7 i metodi, `find_confirmed` e `count_confirmed` inclusi.

  _Requirements: REQ-REG-P01 criteri 2, 5, 6_

---

- [ ] **T-05 — Repository SQLite**

  `SqliteRegistrationRepository` su `<DATA_DIR>/registrations.db`, schema a 7 colonne come in `design.md` §5.4, più:
  - indice `idx_registrations_event_status` su `(event_id, status)`;
  - indice unico **parziale** `uq_registrations_confirmed` su `(user_id, event_id) WHERE status = 'confirmed'` come difesa in profondità.
  - `count_confirmed` implementato con `SELECT COUNT(*) ... WHERE event_id = ? AND status = 'confirmed'`, non filtrando in Python.
  - **Nessun** vincolo `UNIQUE` non condizionato su `(user_id, event_id)`: romperebbe la re-iscrizione dopo cancellazione (REQ-REG-B04 criterio 2).

  _Requirements: REQ-REG-P01 criteri 3, 5, 6, REQ-REG-B04_

---

- [ ] **T-06 — Client HTTP con base condivisa**

  - `clients/base_client.py` — `BaseHttpClient` con `_get(path, resource_id)`: unico modulo che importa `requests`, timeout dal costruttore, error mapping `404` → `ReferenceNotFoundError`, `Timeout`/`ConnectionError`/`RequestException`/`5xx`/status inatteso → `DependencyUnavailableError`. `404` valutato prima di `>= 500`.
  - `clients/user_client.py` — `UserClient(BaseHttpClient).get_user(user_id)` → `_get("/api/v1/users", user_id)`.
  - `clients/event_client.py` — `EventClient(BaseHttpClient).get_event(event_id)` → `_get("/api/v1/events", event_id)`.

  _Requirements: REQ-REG-B01, REQ-REG-B02, REQ-REG-B09_

---

- [ ] **T-07 — Factory e wiring**

  `create_app(repository=None, user_client=None, event_client=None)` costruisce i tre collaboratori da `config` se non iniettati, istanzia `RegistrationService`, registra le route.

  _Requirements: REQ-REG-P01 criterio 4, REQ-REG-P02_

---

- [ ] **T-08 — RegistrationService: creazione con capienza**

  `RegistrationService(repository, user_client, event_client)`, con `self._seat_lock = threading.Lock()`.

  `create_registration(data)` nell'ordine esatto di `design.md` §3.2:
  1. `user_client.get_user(user_id)` — propaga `ReferenceNotFoundError` / `DependencyUnavailableError`
  2. `event = event_client.get_event(event_id)` — idem
  3. `if event["status"] != "published"` → `EventNotOpenError`
  4. **dentro `self._seat_lock`**, senza alcuna I/O di rete:
     - `repository.find_confirmed(user_id, event_id)` non `None` → `AlreadyRegisteredError`
     - `repository.count_confirmed(event_id) >= event["capacity"]` → `EventFullError`
     - costruisce il record con `id` UUID v4, `amount = event["price"]`, `status = "confirmed"`, `created_at == updated_at`, e chiama `repository.save`

  Metodi anche: `get_registration(id)` (→ `RegistrationNotFoundError`), `list_registrations(user_id, event_id, status, page, page_size)` → `(page_items, total)`, `delete_registration(id)`.

  _Requirements: REQ-REG-B01, REQ-REG-B02, REQ-REG-B03, REQ-REG-B04, REQ-REG-B05, REQ-REG-B06, REQ-REG-E01, REQ-REG-E02, REQ-REG-E03, REQ-REG-E05_

---

- [ ] **T-09 — RegistrationService: transizioni di stato e stats**

  - `_ALLOWED_TRANSITIONS = {"confirmed": {"cancelled"}, "cancelled": set()}`.
  - `update_status(registration_id, new_status)`: `RegistrationNotFoundError` se assente; no-op se `new_status == current`; `InvalidStatusTransitionError` se non ammessa; aggiorna `updated_at`. **Nessuna chiamata alle dipendenze.**
  - `get_stats(event_id)`: `event = event_client.get_event(event_id)` (propaga `ReferenceNotFoundError` — la route la tradurrà in `404`, non `422`, perché REQ-REG-B08 criterio 5 lo richiede); `confirmed = repository.count_confirmed(event_id)`; `available = max(0, event["capacity"] - confirmed)`; restituisce i 4 campi.

  _Requirements: REQ-REG-B07, REQ-REG-B08, REQ-REG-E04_

---

- [ ] **T-10 — Route: POST, GET lista e stats**

  - `_validate_create_input(data)` → `user_id` ed `event_id` stringhe non vuote; ignora `amount` e `status`.
  - `_validate_patch_input(data)` → `status` obbligatorio e in `{confirmed, cancelled}`.
  - `_serialize_registration(reg)` → solo i 7 campi del contratto, `amount` come `round(float(...), 2)`.
  - `_paginate(...)`, `_map_domain_error(exc)` con la tabella di `design.md` §4.3.
  - `POST /api/v1/registrations` → 400 / 422 validazione **prima** delle dipendenze / 201 con `Location`.
  - `GET /api/v1/registrations` → filtri `user_id`, `event_id`, `status`; validazione paginazione ed enum → 422.
  - `GET /api/v1/registrations/stats` — **registrata prima** della route con `<registration_id>`. `event_id` mancante → 422; evento inesistente → **404 `NOT_FOUND`**; dipendenza giù → 503.

  _Requirements: REQ-REG-E01, REQ-REG-E02, REQ-REG-B08, REQ-REG-F02_

---

- [ ] **T-11 — Route: GET, PATCH, DELETE singola registrazione**

  - Route `/api/v1/registrations/<registration_id>` registrata con `methods=["GET", "PATCH", "DELETE"]` — il `PUT` non compare, così Werkzeug produce `405` gestito dall'handler di T-02.
  - `GET` → 200 / 404.
  - `PATCH` → validazione `status`; 200 / 404 / 422 (`VALIDATION_ERROR`, `INVALID_STATUS_TRANSITION`).
  - `DELETE` → 204 / 404.

  _Requirements: REQ-REG-E03, REQ-REG-E04, REQ-REG-E05, REQ-REG-E06, REQ-REG-B07_

---

- [ ] **T-12 — Test unitari: repository (tre backend)**

  `tests/test_repository.py`, fixture parametrizzata su memory/json/sqlite.

  Oltre al CRUD, test dedicati alle regole di capienza:
  - `test_count_confirmed_counts_only_confirmed` — mix confirmed/cancelled. REQ-REG-B05
  - `test_count_confirmed_decreases_after_cancel` — REQ-REG-B07
  - `test_count_confirmed_isolated_per_event` — REQ-REG-B05
  - `test_count_confirmed_zero_for_unknown_event` — REQ-REG-B05
  - `test_find_confirmed_ignores_cancelled` — REQ-REG-B04
  - `test_find_confirmed_returns_none_for_other_user` — REQ-REG-B04
  - `test_save_two_rows_same_pair_when_first_cancelled` — verifica che il backend accetti la re-iscrizione dopo cancellazione (critico per SQLite: un UNIQUE non condizionato fallirebbe). REQ-REG-B04
  - CRUD: `save`/`find_by_id`/`find_by_id_not_found`/`list_all` con i tre filtri/`update`/`update_not_found`/`delete`/`delete_not_found`
  - `test_data_dir_created_automatically` per json e sqlite

  _Requirements: REQ-REG-P01, REQ-REG-B04, REQ-REG-B05, REQ-REG-B07_

---

- [ ] **T-13 — Test unitari: client HTTP**

  `tests/test_clients.py` con `responses`, per `UserClient` **e** `EventClient`:
  - 200 → dict; 404 → `ReferenceNotFoundError`; 500 e 503 → `DependencyUnavailableError`; `ConnectionError`; `Timeout`; status inatteso (418).
  - `test_user_client_url_shape` / `test_event_client_url_shape` — l'URL chiamato è `{base}/api/v1/users/{id}` e `{base}/api/v1/events/{id}`, con base URL terminante in slash normalizzata.

  _Requirements: REQ-REG-B01, REQ-REG-B02, REQ-REG-B09_

---

- [ ] **T-14 — Test unitari: business logic e capienza**

  `tests/test_service.py` con `MemoryRegistrationRepository` e fake client che contano le chiamate.

  - `test_create_registration_ok` — `status="confirmed"`, id UUID, timestamps uguali. REQ-REG-E01
  - `test_amount_copied_from_event_price` — REQ-REG-B06
  - `test_amount_in_payload_is_ignored` — REQ-REG-B06 criterio 2
  - `test_amount_zero_price` — REQ-REG-B06 criterio 4
  - `test_user_not_found` — REQ-REG-B01
  - `test_event_not_found` — REQ-REG-B02
  - `test_event_draft_rejected` / `test_event_cancelled_rejected` — `EventNotOpenError`. REQ-REG-B03
  - `test_double_confirmed_registration_rejected` — `AlreadyRegisteredError`. REQ-REG-B04
  - `test_registration_allowed_after_cancellation` — REQ-REG-B04 criterio 2
  - `test_different_user_same_event_allowed` / `test_same_user_different_event_allowed` — REQ-REG-B04 criteri 5-6
  - `test_capacity_reached_rejected` — capacity=2, terza → `EventFullError`. REQ-REG-B05
  - `test_capacity_one_second_rejected` — REQ-REG-B05 criterio 7
  - `test_cancel_frees_seat` — capacity=1, cancella, nuova iscrizione ammessa. REQ-REG-B05 criterio 4, REQ-REG-B07 criterio 3
  - `test_cancelled_not_counted_in_capacity` — REQ-REG-B05 criterio 3
  - `test_transition_confirmed_to_cancelled` — REQ-REG-B07
  - `test_transition_cancelled_to_confirmed_rejected` — REQ-REG-B07 criterio 2
  - `test_transition_same_status_noop` — REQ-REG-B07 criterio 4
  - `test_patch_does_not_call_dependencies` — contatori dei fake invariati. REQ-REG-B07 criterio 7
  - `test_stats_ok` — capacity/confirmed/available. REQ-REG-B08
  - `test_stats_available_clamped_at_zero` — REQ-REG-B08 criterio 4
  - `test_stats_event_not_found` — REQ-REG-B08 criterio 5
  - `test_list_registrations_filters_and_pagination` — REQ-REG-E02
  - `test_delete_frees_seat` — REQ-REG-E05 criterio 3

  _Requirements: REQ-REG-B01..B08, REQ-REG-E01..E05_

---

- [ ] **T-15 — Test unitari: layer HTTP**

  `tests/test_routes.py`, test client Flask, dipendenze mockate con `responses`.

  - health; POST 201 con `Location` e 7 chiavi esatte; 400 JSON malformato; 422 `user_id`/`event_id` mancanti
  - 422 `REFERENCE_NOT_FOUND` per utente ed evento; 422 `EVENT_NOT_OPEN`; 409 `ALREADY_REGISTERED`; 409 `EVENT_FULL`; 503 su `ConnectionError` e su 5xx
  - `test_validation_precedes_dependency_call` — nessun mock registrato, payload invalido → 422 e `len(responses.calls) == 0`
  - GET 200/404; lista 200 con filtri `user_id`/`event_id`/`status`; 422 su `page_size` e `status` invalidi
  - **`test_stats_route_not_shadowed_by_id`** — `GET /api/v1/registrations/stats?event_id=...` restituisce le statistiche e non un 404 da "registrazione con id `stats`". REQ-REG-B08 criterio 8
  - `test_stats_missing_event_id_422`, `test_stats_unknown_event_404`, `test_stats_dependency_down_503`
  - PATCH 200 / 404 / 422 su status invalido / 422 su body senza `status`
  - **`test_put_returns_405`** — corpo conforme allo schema `Error`. REQ-REG-E06
  - DELETE 204 poi 404; DELETE su id inesistente 404

  _Requirements: REQ-REG-00, REQ-REG-B01..B09, REQ-REG-E01..E06, REQ-REG-F02_

---

- [ ] **T-16 — Test di contratto**

  `tests/test_contract.py`: un test per endpoint con `assert_matches_contract("registration-service", ...)`.
  - workspace root in `sys.path`; helper `_adapt(response)` per la Flask test response (il validator non è modificabile).
  - Endpoint: health, POST 201, GET lista, GET stats, GET singola, PATCH, DELETE 204, PUT 405, errore 404, errore 422, errore 503.

  _Requirements: REQ-REG-C01_

---

- [ ] **T-17 — Test di integrazione: solo registration-service**

  `tests/test_integration.py`. Sottoprocesso con `USER_SERVICE_URL` ed `EVENT_SERVICE_URL` su porte chiuse.
  - `test_integration_health` — 200. REQ-REG-00
  - `test_integration_dependency_down_returns_503` — POST → 503. REQ-REG-B09
  - `test_integration_validation_error_without_dependency` — 422 non 503. REQ-REG-F02 criterio 6
  - `test_integration_get_not_found` — 404. REQ-REG-E03
  - `test_integration_put_405` — 405. REQ-REG-E06

  _Requirements: REQ-REG-00, REQ-REG-B09, REQ-REG-E03, REQ-REG-E06, REQ-REG-F02_

---

- [ ] **T-18 — Test di integrazione: tre servizi reali, scenario capienza**

  `tests/test_integration_real.py`. Avvia user-service, event-service e registration-service come processi reali su porte libere, concatenando gli URL. Nessun mock.

  Fixture `live_stack` (scope `module`): avvio nell'ordine user → event → registration, ciascuno con gli `*_SERVICE_URL` dei precedenti; polling `/health` per ognuno; teardown in ordine inverso.

  Scenario completo in un unico test `test_real_capacity_scenario`:
  1. crea organizzatore su user-service
  2. crea evento con `capacity=2` su event-service, poi `PATCH status=published`
  3. crea 4 attendee su user-service
  4. registra attendee 1 → **201**
  5. registra attendee 2 → **201**
  6. registra attendee 3 → **409 `EVENT_FULL`**
  7. `stats` → `capacity=2, confirmed=2, available=0`
  8. `PATCH` la registrazione di attendee 1 a `cancelled` → **200**
  9. `stats` → `confirmed=1, available=1`
  10. registra attendee 4 → **201** (posto liberato)
  11. `stats` → `confirmed=2, available=0`

  Più test separati: `test_real_user_not_found` (422 `REFERENCE_NOT_FOUND`), `test_real_event_not_published` (422 `EVENT_NOT_OPEN`), `test_real_zzz_dependency_down` (spegne event-service → 503; ultimo per ordine alfabetico).

  _Requirements: REQ-REG-B01..B09, REQ-REG-E01, REQ-REG-E04_

---

- [ ] **T-19 — Verifica coverage**

  - `pytest tests/ -v --cov=app --cov-report=term-missing` da `services/registration-service/`.
  - Coverage su `app/` ≥ 80 %.
  - Se inferiore, aggiungi test nei file esistenti.

  _Requirements: REQ-REG-P01, REQ-REG-P02, REQ-REG-C01_
