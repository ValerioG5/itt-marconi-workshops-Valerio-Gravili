# user-service — Tasks

Servizio: **user-service**
Spec: `.kiro/specs/user-service/`
Ordine di esecuzione: sequenziale. Ogni task produce codice compilabile/eseguibile prima di passare al successivo.
Commit atteso per ogni task: `feat(user-service): <descrizione> [T-XX]`

---

- [x] **T-01 — Scaffolding del package e configurazione**

  Crea la struttura di directory e i file scheletro del servizio.

  File da creare:
  - `services/user-service/app/__init__.py` — factory `create_app(repository=None)` vuota (restituisce un'app Flask senza route)
  - `services/user-service/app/__main__.py` — entrypoint che chiama `create_app().run(host="0.0.0.0", port=PORT)`
  - `services/user-service/app/config.py` — legge `PORT` (default 5001), `STORAGE_BACKEND` (default `"memory"`), `DATA_DIR` (default `"./data"`) da `os.environ`
  - `services/user-service/app/routes.py` — modulo vuoto con la funzione `register_routes(app, repository)` stub
  - `services/user-service/app/service.py` — modulo vuoto con la classe `UserService` stub
  - `services/user-service/app/repository/__init__.py` — vuoto
  - `services/user-service/app/repository/base.py` — classe `AbstractUserRepository` con i 6 metodi astratti (`save`, `find_by_id`, `find_by_email`, `list_all`, `update`, `delete`) e le eccezioni `UserNotFoundError`, `EmailAlreadyExistsError`
  - `services/user-service/app/repository/memory.py` — `MemoryUserRepository(AbstractUserRepository)` stub (metodi non ancora implementati, sollevano `NotImplementedError`)
  - `services/user-service/app/repository/json_repo.py` — `JsonUserRepository(AbstractUserRepository)` stub
  - `services/user-service/app/repository/sqlite_repo.py` — `SqliteUserRepository(AbstractUserRepository)` stub
  - `services/user-service/tests/__init__.py` — vuoto
  - `services/user-service/tests/conftest.py` — registra il marker `req` (`pytest.ini_options` o `pytest.mark`)
  - `services/user-service/requirements.txt` — `flask`, `requests`, `pytest`, `pytest-cov`, `responses`

  _Requirements: REQ-USR-P02_

---

- [x] **T-02 — Health endpoint**

  Implementa `GET /health` e l'handler globale per JSON malformato (400).

  - In `routes.py`: aggiungi la route `GET /health` che restituisce `{"status": "ok", "service": "user-service"}` con status 200.
  - In `routes.py`: aggiungi `error_response(code, message, status, details=None)` helper privato che costruisce `{"error": {"code": ..., "message": ..., "details": ...}}`.
  - In `routes.py`: aggiungi l'handler `@app.errorhandler(400)` che risponde con `error.code = "MALFORMED_JSON"`.
  - In `__init__.py`: completa `register_routes(app, repository)` per registrare health e il gestore 400.
  - Il servizio deve essere avviabile con `python -m app` e rispondere a `GET /health`.

  _Requirements: REQ-USR-00, REQ-USR-F02 criterio 1, REQ-USR-C01_

---

- [x] **T-03 — Repository memory**

  Implementa completamente `MemoryUserRepository`.

  - `save(user)`: inserisce `user` nel dizionario `_store` con chiave `user["id"]`; restituisce il dict.
  - `find_by_id(user_id)`: restituisce `_store.get(user_id)` o `None`.
  - `find_by_email(email)`: itera `_store.values()`, restituisce il primo con `u["email"] == email` (confronto su valore già normalizzato) o `None`.
  - `list_all(role, email)`: restituisce lista filtrata; se entrambi i parametri sono `None` restituisce tutti.
  - `update(user)`: sovrascrive `_store[user["id"]]`; solleva `UserNotFoundError` se la chiave non esiste.
  - `delete(user_id)`: rimuove la chiave; solleva `UserNotFoundError` se non esiste.

  _Requirements: REQ-USR-P01 criterio 1_

---

- [x] **T-04 — Repository JSON**

  Implementa completamente `JsonUserRepository`.

  - Costruttore: riceve `data_dir`; crea la directory con `os.makedirs(data_dir, exist_ok=True)`; se `users.json` non esiste lo crea con contenuto `{"users": []}`.
  - Path del file: `os.path.join(data_dir, "users.json")`.
  - `_load() -> list`: apre il file, restituisce `data["users"]`.
  - `_save(users: list)`: sovrascrive il file con `json.dump({"users": users}, f, indent=2)`.
  - Tutti i 6 metodi implementati usando `_load`/`_save` (strategia read-all/write-all).
  - `find_by_email`: confronto case-sensitive su email già normalizzata.
  - `update` e `delete`: sollevano `UserNotFoundError` se l'id non è presente.

  _Requirements: REQ-USR-P01 criteri 2, 5_

---

- [ ] **T-05 — Repository SQLite**

  Implementa completamente `SqliteUserRepository`.

  - Costruttore: riceve `data_dir`; crea la directory; crea il file `users.db` ed esegue `CREATE TABLE IF NOT EXISTS users (...)` con lo schema definito nel design (8 colonne).
  - Tutti i 6 metodi implementati con query parametrizzate (`?` placeholder).
  - `list_all`: costruisce la query con clausole `WHERE` dinamiche per `role` e `email`.
  - `find_by_email`: `SELECT ... WHERE email = ?`.
  - `update`: `UPDATE users SET ... WHERE id = ?`; se `rowcount == 0` solleva `UserNotFoundError`.
  - `delete`: `DELETE FROM users WHERE id = ?`; se `rowcount == 0` solleva `UserNotFoundError`.
  - Ogni metodo apre e chiude la connessione (`with sqlite3.connect(...) as conn`).

  _Requirements: REQ-USR-P01 criteri 3, 5_

---

- [ ] **T-06 — Factory e wiring in `__init__.py`**

  Collega la factory al repository concreto scelto da `STORAGE_BACKEND`.

  - Implementa `_make_repository()` con import lazy per i tre backend.
  - `create_app(repository=None)`: se `repository` è `None` chiama `_make_repository()`; istanzia `UserService(repository)`; chiama `register_routes(app, service)`.
  - `register_routes` riceve il `service` (non il repository direttamente): le route delegano al service.

  _Requirements: REQ-USR-P01 criterio 4, REQ-USR-P02_

---

- [ ] **T-07 — `UserService` e regole di business**

  Implementa la classe `UserService` in `service.py` con tutte le regole `REQ-USR-B*`.

  - Costruttore: `__init__(self, repository: AbstractUserRepository)`.
  - `create_user(data) -> dict`:
    - Normalizza `email` in minuscolo (REQ-USR-B02).
    - Verifica unicità email con `repository.find_by_email` (REQ-USR-B01); solleva `EmailAlreadyExistsError` se esiste.
    - Genera `id = str(uuid.uuid4())`, `now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")`.
    - Applica default `role = "attendee"` se assente, `company = None` se assente.
    - Chiama `repository.save(user_dict)`; restituisce il risultato.
  - `get_user(user_id) -> dict`: chiama `repository.find_by_id`; solleva `UserNotFoundError` se `None`.
  - `list_users(role, email, page, page_size) -> (list[dict], int)`: chiama `repository.list_all(role, email)`; applica slicing per paginazione; restituisce `(page_items, total)`.
  - `replace_user(user_id, data) -> dict`:
    - Verifica esistenza (`find_by_id`); solleva `UserNotFoundError` se assente.
    - Normalizza email (REQ-USR-B02); verifica unicità escludendo `user_id` corrente (REQ-USR-B01).
    - Costruisce dict con tutti i campi mutable sostituiti, mantiene `id` e `created_at` originali, aggiorna `updated_at`.
    - Chiama `repository.update`.
  - `update_user(user_id, data) -> dict`:
    - Verifica esistenza; solleva `UserNotFoundError` se assente.
    - Se `email` è presente in `data`: normalizza (REQ-USR-B02); verifica unicità (REQ-USR-B01).
    - Applica solo i campi presenti in `data` al dict esistente; aggiorna `updated_at`.
    - Chiama `repository.update`.
  - `delete_user(user_id) -> None`: chiama `repository.delete` (propaga `UserNotFoundError`).

  _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03, REQ-USR-F01_

---

- [ ] **T-08 — Route POST e GET lista**

  Implementa in `routes.py` le route di creazione e lista utenti.

  - Helper privato `_validate_user_input(data, partial=False) -> list[str]`: restituisce lista di messaggi di errore; se `partial=True` salta i controlli di obbligatorietà (per PATCH).
    - `first_name`: obbligatorio se non partial, 1–50 caratteri.
    - `last_name`: obbligatorio se non partial, 1–50 caratteri.
    - `email`: obbligatorio se non partial; deve contenere `@` e un dominio (es. regex `r'^[^@]+@[^@]+\.[^@]+$'`).
    - `company`: se presente, max 100 caratteri.
    - `role`: se presente, deve essere in `{"attendee", "speaker", "organizer"}`.
  - Helper privato `paginate(items, page, page_size) -> dict`: restituisce `{"items": ..., "page": ..., "page_size": ..., "total": ...}`.
  - `POST /api/v1/users`:
    - Parsing con `request.get_json(force=True, silent=False)` (lancia 400 se malformato).
    - Validazione con `_validate_user_input`; se errori → 422 `VALIDATION_ERROR`.
    - Chiama `service.create_user(data)`; gestisce `EmailAlreadyExistsError` → 409.
    - Risponde 201 con header `Location: /api/v1/users/<id>`.
  - `GET /api/v1/users`:
    - Legge `page`, `page_size`, `role`, `email` da `request.args`.
    - Valida `page >= 1`, `1 <= page_size <= 100`, `role` in enum se presente; altrimenti 422.
    - Chiama `service.list_users(role, email, page, page_size)`.
    - Risponde 200 con body paginato.

  _Requirements: REQ-USR-E01, REQ-USR-E02, REQ-USR-F02, REQ-USR-B03_

---

- [ ] **T-09 — Route GET, PUT, PATCH, DELETE per singolo utente**

  Implementa in `routes.py` le restanti route su `/api/v1/users/<id>`.

  - `GET /api/v1/users/<id>`: chiama `service.get_user(id)`; gestisce `UserNotFoundError` → 404 `NOT_FOUND`; risponde 200.
  - `PUT /api/v1/users/<id>`:
    - Parsing + validazione completa (non partial).
    - Chiama `service.replace_user(id, data)`.
    - Gestisce `UserNotFoundError` → 404, `EmailAlreadyExistsError` → 409.
    - Risponde 200.
  - `PATCH /api/v1/users/<id>`:
    - Parsing + validazione partial (`partial=True`).
    - Chiama `service.update_user(id, data)`.
    - Gestisce `UserNotFoundError` → 404, `EmailAlreadyExistsError` → 409.
    - Risponde 200.
  - `DELETE /api/v1/users/<id>`:
    - Chiama `service.delete_user(id)`.
    - Gestisce `UserNotFoundError` → 404.
    - Risponde 204 senza body.
  - Serializzazione output: la funzione `_serialize_user(user: dict) -> dict` estrae solo i campi del contratto (`id`, `first_name`, `last_name`, `email`, `company`, `role`, `created_at`, `updated_at`) — nessun campo extra.

  _Requirements: REQ-USR-E03, REQ-USR-E04, REQ-USR-E05, REQ-USR-E06, REQ-USR-C01_

---

- [ ] **T-10 — Test unitari: repository (tutti e tre i backend)**

  Scrivi `tests/test_repository.py`.

  - Fixture parametrizzata `repo` che istanzia `MemoryUserRepository()`, `JsonUserRepository(tmp_path)`, `SqliteUserRepository(tmp_path)` — ogni test gira 3 volte.
  - Test da includere (con marker `@pytest.mark.req`):
    - `test_save_and_find_by_id` — salva un utente, lo recupera per id. `@pytest.mark.req("REQ-USR-P01")`
    - `test_find_by_email` — trova per email normalizzata. `@pytest.mark.req("REQ-USR-B02")`
    - `test_find_by_email_not_found` — restituisce `None` se assente. `@pytest.mark.req("REQ-USR-P01")`
    - `test_list_all_no_filter` — restituisce tutti. `@pytest.mark.req("REQ-USR-E02")`
    - `test_list_all_filter_role` — filtra per role. `@pytest.mark.req("REQ-USR-B03")`
    - `test_list_all_filter_email` — filtra per email. `@pytest.mark.req("REQ-USR-B03")`
    - `test_update` — aggiorna un campo; verifica il risultato. `@pytest.mark.req("REQ-USR-E04")`
    - `test_update_not_found` — solleva `UserNotFoundError`. `@pytest.mark.req("REQ-USR-E04")`
    - `test_delete` — rimuove; poi `find_by_id` restituisce `None`. `@pytest.mark.req("REQ-USR-E06")`
    - `test_delete_not_found` — solleva `UserNotFoundError`. `@pytest.mark.req("REQ-USR-E06")`
    - `test_data_dir_created_automatically` — skippa per memory; verifica che `data_dir` esista dopo il costruttore per json e sqlite. `@pytest.mark.req("REQ-USR-P01")`

  _Requirements: REQ-USR-P01, REQ-USR-B02, REQ-USR-B03_

---

- [ ] **T-11 — Test unitari: business logic (`test_service.py`)**

  Scrivi `tests/test_service.py`.

  - Fixture `svc`: `UserService(MemoryUserRepository())` fresco per ogni test.
  - Test da includere:
    - `test_create_user_ok` — crea utente; verifica `id` UUID, `role="attendee"` default, `email` lowercase. `@pytest.mark.req("REQ-USR-B02", "REQ-USR-F01")`
    - `test_create_user_email_lowercase` — email con maiuscole → email salvata in minuscolo. `@pytest.mark.req("REQ-USR-B02")`
    - `test_create_user_duplicate_email` — seconda creazione con stessa email (case diversa) → `EmailAlreadyExistsError`. `@pytest.mark.req("REQ-USR-B01")`
    - `test_get_user_not_found` — id inesistente → `UserNotFoundError`. `@pytest.mark.req("REQ-USR-E03")`
    - `test_list_users_filter_role` — crea utenti con role diverse; verifica filtro. `@pytest.mark.req("REQ-USR-B03")`
    - `test_list_users_pagination` — crea 5 utenti; verifica `page=1, page_size=2` → 2 risultati, `total=5`. `@pytest.mark.req("REQ-USR-E02")`
    - `test_replace_user_ok` — PUT con nuovi dati; `created_at` invariato, `updated_at` aggiornato. `@pytest.mark.req("REQ-USR-E04")`
    - `test_replace_user_email_conflict` — PUT con email di un altro utente → `EmailAlreadyExistsError`. `@pytest.mark.req("REQ-USR-B01")`
    - `test_update_user_partial` — PATCH solo `company`; altri campi invariati. `@pytest.mark.req("REQ-USR-E05")`
    - `test_delete_user_ok` — DELETE; poi `get_user` → `UserNotFoundError`. `@pytest.mark.req("REQ-USR-E06")`

  _Requirements: REQ-USR-B01, REQ-USR-B02, REQ-USR-B03, REQ-USR-E02, REQ-USR-E03, REQ-USR-E04, REQ-USR-E05, REQ-USR-E06_

---

- [ ] **T-12 — Test unitari: layer HTTP (`test_routes.py`)**

  Scrivi `tests/test_routes.py`.

  - Fixture `client`: `create_app(MemoryUserRepository()).test_client()`.
  - Test da includere:
    - `test_post_user_201` — body valido → 201, header `Location` presente, `email` in lowercase nel body. `@pytest.mark.req("REQ-USR-E01")`
    - `test_post_user_422_missing_field` — body senza `last_name` → 422 `VALIDATION_ERROR`. `@pytest.mark.req("REQ-USR-F02")`
    - `test_post_user_422_invalid_email` — email senza `@` → 422. `@pytest.mark.req("REQ-USR-F02")`
    - `test_post_user_422_invalid_role` — `role="god"` → 422. `@pytest.mark.req("REQ-USR-F02")`
    - `test_post_user_400_malformed_json` — corpo `"{bad"` → 400 `MALFORMED_JSON`. `@pytest.mark.req("REQ-USR-F02")`
    - `test_post_user_409_duplicate_email` — due POST con stessa email → 409 `EMAIL_ALREADY_EXISTS`. `@pytest.mark.req("REQ-USR-B01")`
    - `test_get_user_200` — GET per id esistente → 200 con body corretto. `@pytest.mark.req("REQ-USR-E03")`
    - `test_get_user_404` — GET per id inesistente → 404 `NOT_FOUND`. `@pytest.mark.req("REQ-USR-E03")`
    - `test_list_users_200` — GET lista → 200, struttura paginata. `@pytest.mark.req("REQ-USR-E02")`
    - `test_list_users_422_bad_page_size` — `page_size=200` → 422. `@pytest.mark.req("REQ-USR-E02")`
    - `test_put_user_200` — PUT valido → 200, `updated_at` presente. `@pytest.mark.req("REQ-USR-E04")`
    - `test_put_user_404` — PUT su id inesistente → 404. `@pytest.mark.req("REQ-USR-E04")`
    - `test_patch_user_200` — PATCH `company` → 200, solo `company` cambiato. `@pytest.mark.req("REQ-USR-E05")`
    - `test_delete_user_204` — DELETE → 204, poi GET → 404. `@pytest.mark.req("REQ-USR-E06")`
    - `test_health_200` — GET `/health` → 200 `{"status":"ok","service":"user-service"}`. `@pytest.mark.req("REQ-USR-00")`

  _Requirements: REQ-USR-00, REQ-USR-E01, REQ-USR-E02, REQ-USR-E03, REQ-USR-E04, REQ-USR-E05, REQ-USR-E06, REQ-USR-F02, REQ-USR-B01_

---

- [ ] **T-13 — Test di contratto (`test_contract.py`)**

  Scrivi `tests/test_contract.py` verificando ogni endpoint contro `contracts/openapi/user-service.yaml` tramite `assert_matches_contract`.

  - Fixture `client`: `create_app(MemoryUserRepository()).test_client()`.
  - Import: `from contracts.validator import assert_matches_contract` (il `sys.path` deve includere la root del repo; aggiungilo in `conftest.py` se necessario).
  - Test da includere (uno per endpoint, risposta di successo):
    - `test_contract_health` — `GET /health` → `assert_matches_contract("user-service", "GET", "/health", resp)`. `@pytest.mark.req("REQ-USR-C01")`
    - `test_contract_post_user` — `POST /api/v1/users` valido → contratto 201. `@pytest.mark.req("REQ-USR-C01")`
    - `test_contract_get_user` — `GET /api/v1/users/{id}` → contratto 200. `@pytest.mark.req("REQ-USR-C01")`
    - `test_contract_list_users` — `GET /api/v1/users` → contratto 200. `@pytest.mark.req("REQ-USR-C01")`
    - `test_contract_put_user` — `PUT /api/v1/users/{id}` → contratto 200. `@pytest.mark.req("REQ-USR-C01")`
    - `test_contract_patch_user` — `PATCH /api/v1/users/{id}` → contratto 200. `@pytest.mark.req("REQ-USR-C01")`
    - `test_contract_delete_user` — `DELETE /api/v1/users/{id}` → contratto 204. `@pytest.mark.req("REQ-USR-C01")`
    - `test_contract_error_404` — `GET /api/v1/users/<unknown>` → contratto Error 404. `@pytest.mark.req("REQ-USR-C01")`

  _Requirements: REQ-USR-C01_

---

- [ ] **T-14 — Test di integrazione (`test_integration.py`)**

  Scrivi `tests/test_integration.py` che avvia il servizio reale come sottoprocesso.

  - Fixture `live_url` (scope `module`):
    1. Trova porta libera: `s = socket.socket(); s.bind(("", 0)); port = s.getsockname()[1]; s.close()`.
    2. Avvia: `proc = subprocess.Popen(["python", "-m", "app"], cwd=<path_to_user_service>, env={**os.environ, "PORT": str(port), "STORAGE_BACKEND": "memory"})`.
    3. Polling `GET /health` ogni 0.2 s fino a timeout 10 s.
    4. `yield f"http://localhost:{port}"`.
    5. Teardown: `proc.terminate(); proc.wait(timeout=5)`.
  - Test da includere:
    - `test_integration_create_and_get` — POST → 201, poi GET per id → 200, campi corretti. `@pytest.mark.req("REQ-USR-E01", "REQ-USR-E03")`
    - `test_integration_get_not_found` — GET id inesistente → 404 `NOT_FOUND`. `@pytest.mark.req("REQ-USR-E03")`
    - `test_integration_duplicate_email` — due POST stessa email → secondo → 409 `EMAIL_ALREADY_EXISTS`. `@pytest.mark.req("REQ-USR-B01")`
    - `test_integration_health` — GET `/health` → 200 `{"status": "ok", "service": "user-service"}`. `@pytest.mark.req("REQ-USR-00")`

  _Requirements: REQ-USR-00, REQ-USR-E01, REQ-USR-E03, REQ-USR-B01_

---

- [ ] **T-15 — Verifica coverage e `requirements.txt`**

  Esegui la suite completa e verifica la copertura.

  - Dalla directory `services/user-service/`, esegui: `pytest tests/ -v --cov=app --cov-report=term-missing`.
  - La coverage su `app/` deve essere ≥ 80 %.
  - Se la coverage è inferiore, aggiungi i test mancanti nei file già esistenti (non creare nuovi file di test).
  - Verifica che `requirements.txt` contenga tutte le dipendenze necessarie e che `pip install -r requirements.txt` non produca errori.

  _Requirements: REQ-USR-P01, REQ-USR-P02, REQ-USR-C01_
