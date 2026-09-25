# event-service — Tasks

Servizio: **event-service**
Ordine: sequenziale. Ogni task lascia il codice in stato eseguibile.
Commit per task: `feat(event-service): <descrizione> [T-XX]`

---

- [ ] **T-01 — Scaffolding del package e configurazione**

  Crea la struttura di directory e i file scheletro.

  - `services/event-service/app/__init__.py` — `create_app(repository=None, user_client=None)` che restituisce un'app Flask
  - `services/event-service/app/__main__.py` — entrypoint `create_app().run(host="0.0.0.0", port=PORT)`
  - `services/event-service/app/config.py` — `PORT` (default 5002), `USER_SERVICE_URL` (default `http://localhost:5001`), `STORAGE_BACKEND` (default `memory`), `DATA_DIR` (default `./data`), `DEPENDENCY_TIMEOUT = 2`
  - `services/event-service/app/routes.py` — stub `register_routes(app, service)`
  - `services/event-service/app/service.py` — stub classe `EventService(repository, user_client)`
  - `services/event-service/app/clients/__init__.py` — vuoto
  - `services/event-service/app/clients/user_client.py` — stub classe `UserClient(base_url, timeout)`
  - `services/event-service/app/repository/__init__.py` — vuoto
  - `services/event-service/app/repository/base.py` — `AbstractEventRepository` con 5 metodi astratti (`save`, `find_by_id`, `list_all`, `update`, `delete`) e le eccezioni `EventNotFoundError`, `OrganizerNotFoundError`, `InvalidOrganizerError`, `InvalidStatusTransitionError`, `ValidationError`, `DependencyUnavailableError`
  - `services/event-service/app/repository/memory.py`, `json_repo.py`, `sqlite_repo.py` — stub che sollevano `NotImplementedError`
  - `services/event-service/tests/__init__.py` — vuoto
  - `services/event-service/tests/conftest.py` — registra il marker `req`
  - `services/event-service/requirements.txt` — `flask`, `requests`, `pytest`, `pytest-cov`, `responses`, `pyyaml`, `jsonschema`

  _Requirements: REQ-EVT-P02_

---

- [ ] **T-02 — Health endpoint e handler 400**

  - In `routes.py`: helper `_error_response(code, message, status, details=None)`.
  - Route `GET /health` → `{"status": "ok", "service": "event-service"}` con 200.
  - Handler `@app.errorhandler(400)` → `error.code = "MALFORMED_JSON"`.
  - Il servizio deve essere avviabile con `python -m app` e rispondere a `GET /health`.

  _Requirements: REQ-EVT-00, REQ-EVT-F02 criterio 1, REQ-EVT-C01_

---

- [ ] **T-03 — Repository memory**

  Implementa `MemoryEventRepository`:
  - `save(event)` → inserisce in `_store[event["id"]]`, restituisce copia.
  - `find_by_id(event_id)` → copia o `None`.
  - `list_all(status, city)` → lista filtrata con AND logic; entrambi `None` → tutti.
  - `update(event)` → sovrascrive; `EventNotFoundError` se l'id non esiste.
  - `delete(event_id)` → rimuove; `EventNotFoundError` se non esiste.

  _Requirements: REQ-EVT-P01 criterio 1_

---

- [ ] **T-04 — Repository JSON**

  Implementa `JsonEventRepository`:
  - Costruttore: `os.makedirs(data_dir, exist_ok=True)`; crea `<data_dir>/events.json` con `{"events": []}` se assente.
  - `_load()` / `_save(events)` con `json` stdlib, strategia read-all/write-all.
  - I 5 metodi implementati su `_load`/`_save`.
  - `update` e `delete` sollevano `EventNotFoundError` se l'id non è presente.

  _Requirements: REQ-EVT-P01 criteri 2, 5_

---

- [ ] **T-05 — Repository SQLite**

  Implementa `SqliteEventRepository`:
  - Costruttore: crea la directory e la tabella `events` con le 13 colonne dello schema in `design.md`.
  - Query parametrizzate con placeholder `?`.
  - `list_all` costruisce clausole `WHERE` dinamiche per `status` e `city`.
  - `update` / `delete`: `rowcount == 0` → `EventNotFoundError`.
  - Connessione aperta e chiusa per ogni operazione (`try/finally`).
  - Helper `_row_to_dict` per mappare la tupla sul dict con le 13 chiavi.

  _Requirements: REQ-EVT-P01 criteri 3, 5_

---

- [ ] **T-06 — UserClient con error mapping**

  Implementa `clients/user_client.py` — **unico** modulo che importa `requests`.

  - `__init__(self, base_url, timeout=2)`: normalizza `base_url` con `rstrip("/")`.
  - `get_user(user_id) -> dict`: chiama `GET {base_url}/api/v1/users/{user_id}` con `timeout=self._timeout`.
  - Error mapping obbligatorio:
    - `requests.Timeout` → `DependencyUnavailableError`
    - `requests.ConnectionError` → `DependencyUnavailableError`
    - `requests.RequestException` (catch-all) → `DependencyUnavailableError`
    - status `404` → `OrganizerNotFoundError`
    - status `>= 500` → `DependencyUnavailableError`
    - status diverso da `200` → `DependencyUnavailableError`
    - status `200` → `resp.json()`
  - L'ordine dei controlli conta: `404` valutato **prima** di `>= 500`.

  _Requirements: REQ-EVT-B01, REQ-EVT-B05_

---

- [ ] **T-07 — Factory e wiring**

  In `__init__.py`:
  - `_make_repository()` con import lazy per i tre backend.
  - `create_app(repository=None, user_client=None)`: costruisce il repository e il `UserClient(config.USER_SERVICE_URL, config.DEPENDENCY_TIMEOUT)` se non iniettati, istanzia `EventService(repository, user_client)`, chiama `register_routes(app, service)`.
  - Entrambi i parametri devono essere iniettabili per i test.

  _Requirements: REQ-EVT-P01 criterio 4, REQ-EVT-P02_

---

- [ ] **T-08 — EventService: creazione e regole organizzatore**

  In `service.py`, classe `EventService(repository, user_client)`:

  - Helper `_now()` → `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")`.
  - Helper `_assert_valid_organizer(organizer_id)`: chiama `user_client.get_user`; se `user["role"] != "organizer"` solleva `InvalidOrganizerError`.
  - `create_event(data) -> dict`:
    - valida coerenza date (`end_date >= start_date`) → `ValidationError`
    - chiama `_assert_valid_organizer(data["organizer_id"])`
    - genera `id` UUID v4, `created_at` = `updated_at` = `_now()`
    - default `status = "draft"`, `description = None`
    - chiama `repository.save`
  - `get_event(event_id) -> dict`: `EventNotFoundError` se assente.
  - `list_events(status, city, page, page_size) -> (list, int)`: delega a `repository.list_all`, applica slicing di paginazione, restituisce `(page_items, total)`.
  - `delete_event(event_id) -> None`: delega a `repository.delete`.

  _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-F01, REQ-EVT-E01, REQ-EVT-E02, REQ-EVT-E03, REQ-EVT-E06_

---

- [ ] **T-09 — EventService: transizioni di stato e update**

  Aggiungi a `service.py`:

  - Costante `_ALLOWED_TRANSITIONS = {"draft": {"published", "cancelled"}, "published": {"cancelled"}, "cancelled": set()}`.
  - Helper `_assert_valid_transition(current, requested)`: no-op se `requested == current`; altrimenti `InvalidStatusTransitionError` se `requested not in _ALLOWED_TRANSITIONS[current]`.
  - `replace_event(event_id, data) -> dict`:
    - verifica esistenza → `EventNotFoundError`
    - valida coerenza date sul payload
    - valida organizzatore
    - se `status` presente: `_assert_valid_transition(existing["status"], data["status"])`; se assente preserva lo status stored
    - mantiene `id` e `created_at`, aggiorna `updated_at`
  - `update_event(event_id, data) -> dict`:
    - verifica esistenza → `EventNotFoundError`
    - date: valida sul **merge** tra stored e nuovo (`data.get("start_date", existing["start_date"])` e analogo per `end_date`)
    - se `organizer_id` presente: valida; se assente **non** chiamare user-service
    - se `status` presente: applica `_assert_valid_transition`
    - applica solo i campi presenti in `data`, aggiorna `updated_at`

  _Requirements: REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-E04, REQ-EVT-E05_

---

- [ ] **T-10 — Route: validazione, POST e GET lista**

  In `routes.py`:

  - Helper `_validate_event_input(data, partial=False) -> list[str]` con tutte le regole di REQ-EVT-F02: `title` 3–120, `description` ≤ 2000, `organizer_id` presente, `venue` ≤ 100, `city` ≤ 60, `start_date`/`end_date` regex `^\d{4}-\d{2}-\d{2}$`, `capacity` int 1–10000, `price` numero ≥ 0, `status` in enum.
  - Helper `_serialize_event(event) -> dict` con **solo** i 12 campi del contratto; `price` arrotondato a 2 decimali con `round(float(price), 2)`.
  - Helper `_paginate(page_items, page, page_size, total) -> dict`.
  - `POST /api/v1/events`: parsing (400 se malformato) → validazione campi (422) → `service.create_event` → 201 con header `Location`. Mappa `OrganizerNotFoundError`→422 `REFERENCE_NOT_FOUND`, `InvalidOrganizerError`→422 `INVALID_ORGANIZER`, `ValidationError`→422 `VALIDATION_ERROR`, `DependencyUnavailableError`→503 `DEPENDENCY_UNAVAILABLE`.
  - `GET /api/v1/events`: valida `page >= 1`, `1 <= page_size <= 100`, `status` in enum → 422; poi `service.list_events` → 200.
  - **La validazione dei campi deve precedere la chiamata a user-service.**

  _Requirements: REQ-EVT-E01, REQ-EVT-E02, REQ-EVT-F02, REQ-EVT-B06_

---

- [ ] **T-11 — Route: GET, PUT, PATCH, DELETE su singolo evento**

  In `routes.py`:

  - `GET /api/v1/events/<event_id>` → 200 / 404 `NOT_FOUND`.
  - `PUT /api/v1/events/<event_id>` → validazione completa; 200 / 404 / 422 (`VALIDATION_ERROR`, `REFERENCE_NOT_FOUND`, `INVALID_ORGANIZER`, `INVALID_STATUS_TRANSITION`) / 503.
  - `PATCH /api/v1/events/<event_id>` → validazione parziale (`partial=True`); stessi codici del PUT.
  - `DELETE /api/v1/events/<event_id>` → 204 senza body / 404.
  - Tutte le risposte di successo passano da `_serialize_event`.

  _Requirements: REQ-EVT-E03, REQ-EVT-E04, REQ-EVT-E05, REQ-EVT-E06, REQ-EVT-B04, REQ-EVT-C01_

---

- [ ] **T-12 — Test unitari: repository (tre backend)**

  Crea `tests/test_repository.py` con fixture parametrizzata su `memory`, `json` (`tmp_path`), `sqlite` (`tmp_path`).

  Test, ognuno con marker `@pytest.mark.req(...)`:
  - `test_save_and_find_by_id` — REQ-EVT-P01
  - `test_find_by_id_not_found` — REQ-EVT-E03
  - `test_list_all_no_filter` — REQ-EVT-E02
  - `test_list_all_filter_status` — REQ-EVT-B06
  - `test_list_all_filter_city` — REQ-EVT-B06
  - `test_list_all_filter_both` — REQ-EVT-B06
  - `test_update` — REQ-EVT-E04
  - `test_update_not_found` — REQ-EVT-E04
  - `test_delete` — REQ-EVT-E06
  - `test_delete_not_found` — REQ-EVT-E06
  - `test_data_dir_created_automatically` (json + sqlite) — REQ-EVT-P01

  _Requirements: REQ-EVT-P01, REQ-EVT-B06, REQ-EVT-E02, REQ-EVT-E03, REQ-EVT-E04, REQ-EVT-E06_

---

- [ ] **T-13 — Test unitari: UserClient con `responses`**

  Crea `tests/test_user_client.py`. Copre la tabella di error mapping di `design.md` §3.3 usando `responses`:

  - `test_get_user_ok` — 200 → dict restituito. REQ-EVT-B01
  - `test_get_user_404_raises_organizer_not_found` — 404 → `OrganizerNotFoundError`. REQ-EVT-B01
  - `test_get_user_500_raises_dependency_unavailable` — 500 → `DependencyUnavailableError`. REQ-EVT-B05
  - `test_get_user_connection_error` — `body=requests.ConnectionError(...)` → `DependencyUnavailableError`. REQ-EVT-B05
  - `test_get_user_timeout` — `body=requests.Timeout(...)` → `DependencyUnavailableError`. REQ-EVT-B05
  - `test_get_user_uses_configured_base_url` — verifica che l'URL chiamato sia `{base_url}/api/v1/users/{id}`. REQ-EVT-B05 criterio 6
  - `test_timeout_is_passed` — verifica che il timeout configurato sia effettivamente usato.

  _Requirements: REQ-EVT-B01, REQ-EVT-B05_

---

- [ ] **T-14 — Test unitari: business logic**

  Crea `tests/test_service.py`. Usa `MemoryEventRepository` e una classe `FakeUserClient` locale (iniettata), senza Flask e senza rete.

  - `test_create_event_ok` — id UUID, `status="draft"`, timestamps uguali. REQ-EVT-F01, REQ-EVT-E01
  - `test_create_event_organizer_not_found` — fake che solleva `OrganizerNotFoundError`. REQ-EVT-B01
  - `test_create_event_invalid_organizer_role` — fake che restituisce `role="attendee"` → `InvalidOrganizerError`. REQ-EVT-B02
  - `test_create_event_dependency_unavailable` — fake che solleva `DependencyUnavailableError`. REQ-EVT-B05
  - `test_create_event_end_before_start` — `ValidationError`. REQ-EVT-B03
  - `test_create_event_same_day_ok` — `end_date == start_date` accettato. REQ-EVT-B03
  - `test_transition_draft_to_published` / `test_transition_draft_to_cancelled` / `test_transition_published_to_cancelled` — ammesse. REQ-EVT-B04
  - `test_transition_published_to_draft_rejected` — `InvalidStatusTransitionError`. REQ-EVT-B04
  - `test_transition_from_cancelled_rejected` — stato terminale. REQ-EVT-B04
  - `test_transition_same_status_is_noop` — accettata. REQ-EVT-B04
  - `test_patch_only_start_date_validates_against_stored_end` — merge. REQ-EVT-B03
  - `test_patch_only_end_date_validates_against_stored_start` — merge. REQ-EVT-B03
  - `test_patch_without_organizer_id_does_not_call_user_service` — il fake registra le chiamate; asserisce zero chiamate. REQ-EVT-B01 criterio 5
  - `test_list_events_pagination` — REQ-EVT-E02
  - `test_delete_event_then_get_raises` — REQ-EVT-E06

  _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B03, REQ-EVT-B04, REQ-EVT-B05, REQ-EVT-E02, REQ-EVT-E06_

---

- [ ] **T-15 — Test unitari: layer HTTP con `responses`**

  Crea `tests/test_routes.py`. Flask test client con `MemoryEventRepository`; chiamate a user-service mockate con `responses`.

  - `test_health_200` — REQ-EVT-00
  - `test_post_event_201` — 201, header `Location`, `status="draft"`. REQ-EVT-E01
  - `test_post_event_422_missing_title` / `_title_too_short` / `_bad_capacity` / `_negative_price` / `_bad_date_format` / `_invalid_status` — REQ-EVT-F02
  - `test_post_event_400_malformed_json` — REQ-EVT-F02
  - `test_post_event_422_end_before_start` — REQ-EVT-B03
  - `test_post_event_422_reference_not_found` — mock 404 → `REFERENCE_NOT_FOUND`. REQ-EVT-B01
  - `test_post_event_422_invalid_organizer` — mock 200 `role=attendee` → `INVALID_ORGANIZER`. REQ-EVT-B02
  - `test_post_event_503_connection_error` — mock `ConnectionError` → `DEPENDENCY_UNAVAILABLE`. REQ-EVT-B05
  - `test_post_event_503_on_5xx` — mock 500 → 503. REQ-EVT-B05
  - `test_validation_precedes_dependency_call` — payload invalido **senza** registrare alcun mock: deve rispondere 422 e non 503. REQ-EVT-E01 criterio 4
  - `test_get_event_200` / `test_get_event_404` — REQ-EVT-E03
  - `test_list_events_200` / `test_list_events_filter_status_city` / `test_list_events_422_bad_page_size` — REQ-EVT-E02, REQ-EVT-B06
  - `test_put_event_200` / `test_put_event_404` — REQ-EVT-E04
  - `test_patch_event_200` / `test_patch_status_published_then_draft_422` — REQ-EVT-E05, REQ-EVT-B04
  - `test_delete_event_204_then_404` — REQ-EVT-E06

  _Requirements: REQ-EVT-00, REQ-EVT-B01..B06, REQ-EVT-E01..E06, REQ-EVT-F02_

---

- [ ] **T-16 — Test di contratto**

  Crea `tests/test_contract.py`: almeno un test per endpoint con `assert_matches_contract("event-service", method, path, response)`.

  - Aggiungi la workspace root a `sys.path` per importare `contracts.validator`.
  - Helper `_adapt(flask_response) -> dict` che converte la risposta Flask nel formato `{"status_code", "headers", "json"}` atteso dal validator (la Flask test response espone `.json` come proprietà, non come metodo; il validator non è modificabile).
  - Mocka user-service con `responses` dove serve.

  Test: `health`, `post_event` (201), `get_event` (200), `list_events` (200), `put_event` (200), `patch_event` (200), `delete_event` (204), `error_404`, `error_422_reference_not_found`, `error_503`.

  _Requirements: REQ-EVT-C01_

---

- [ ] **T-17 — Test di integrazione: event-service da solo**

  Crea `tests/test_integration.py`. Avvia il solo event-service come sottoprocesso (`sys.executable -m app`) su porta libera, `STORAGE_BACKEND=memory`, con `USER_SERVICE_URL` puntato a una **porta chiusa**.

  - Fixture `live_url` (scope `module`): porta libera via `socket`, `subprocess.Popen` con `cwd` = service root e `PYTHONPATH` che include la service root; polling `/health` fino a 15 s; teardown `terminate()` + `wait(timeout=5)`.
  - `test_integration_health` — 200. REQ-EVT-00
  - `test_integration_dependency_down_returns_503` — POST evento → 503 `DEPENDENCY_UNAVAILABLE`. REQ-EVT-B05
  - `test_integration_validation_error_without_dependency` — payload invalido → 422, non 503. REQ-EVT-E01 criterio 4
  - `test_integration_get_not_found` — 404. REQ-EVT-E03

  _Requirements: REQ-EVT-00, REQ-EVT-B05, REQ-EVT-E01, REQ-EVT-E03_

---

- [ ] **T-18 — Test di integrazione: user-service + event-service reali**

  Crea `tests/test_integration_real.py`. Avvia **due** processi reali su porte libere: prima user-service, poi event-service con `USER_SERVICE_URL` puntato alla porta effettiva di user-service. Nessun mock.

  - Fixture `live_stack` (scope `module`): avvia entrambi, attende entrambi gli `/health`, restituisce `(user_url, event_url, user_proc)`; teardown in ordine inverso.
  - `test_real_create_event_with_valid_organizer` — crea un utente `role=organizer` via user-service, poi POST evento → **201**, `status="draft"`. REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-E01
  - `test_real_organizer_not_found` — `organizer_id` UUID casuale → **422 `REFERENCE_NOT_FOUND`**. REQ-EVT-B01
  - `test_real_invalid_organizer_role` — utente `role=attendee` → **422 `INVALID_ORGANIZER`**. REQ-EVT-B02
  - `test_real_user_service_down` — termina il processo user-service, poi POST evento → **503 `DEPENDENCY_UNAVAILABLE`**. Da eseguire **per ultimo** (spegne una dipendenza condivisa). REQ-EVT-B05

  _Requirements: REQ-EVT-B01, REQ-EVT-B02, REQ-EVT-B05, REQ-EVT-E01_

---

- [ ] **T-19 — Verifica coverage**

  - Da `services/event-service/`: `pytest tests/ -v --cov=app --cov-report=term-missing`.
  - La coverage su `app/` deve essere ≥ 80 %.
  - Se inferiore, aggiungi test nei file esistenti (non crearne di nuovi).
  - Verifica che `pip install -r requirements.txt` non produca errori.

  _Requirements: REQ-EVT-P01, REQ-EVT-P02, REQ-EVT-C01_
