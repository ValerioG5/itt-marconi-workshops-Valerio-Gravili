# user-service — Requirements

Servizio: **user-service**
Base path: `/api/v1/users`
Porta di sviluppo: `5001`
Tipo: Obbligatorio
Contratto: `contracts/openapi/user-service.yaml`

---

## REQ-USR-00 — Health check

**User story:** As an operator, I want a health endpoint so that the test harness and monitoring tools can verify the service is running before sending traffic.

**Acceptance criteria**

1. WHEN a client sends `GET /health` THE user-service SHALL respond `200` with body `{"status": "ok", "service": "user-service"}`.
2. THE user-service SHALL return the health response even when the storage backend is empty.

---

## REQ-USR-F01 — Struttura della risorsa User

**User story:** As a consumer of the API, I want every user resource to carry a stable set of fields so that I can rely on a consistent shape in every response.

**Acceptance criteria**

1. THE user-service SHALL include in every User response the fields: `id`, `first_name`, `last_name`, `email`, `role`, `created_at`, `updated_at`.
2. THE user-service SHALL generate `id` as UUID v4 server-side; it SHALL NOT accept `id` from the client in any request body.
3. THE user-service SHALL set `created_at` and `updated_at` to the current UTC timestamp in ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`) at creation time.
4. THE user-service SHALL include `company` in the User response; its value MAY be `null` if not provided.
5. THE user-service SHALL NOT include fields beyond those defined in `contracts/openapi/user-service.yaml` (`additionalProperties: false`).

---

## REQ-USR-F02 — Validazione dei campi in input

**User story:** As an API client, I want the service to reject malformed or incomplete payloads immediately so that I receive clear feedback about what is wrong.

**Acceptance criteria**

1. WHEN a request body is not valid JSON THE user-service SHALL respond `400` with `{"error": {"code": "MALFORMED_JSON", "message": "...", "details": {}}}`.
2. WHEN `first_name` is absent or empty THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
3. WHEN `first_name` exceeds 50 characters THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
4. WHEN `last_name` is absent or empty THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
5. WHEN `last_name` exceeds 50 characters THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
6. WHEN `email` is absent THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
7. WHEN `email` does not match a valid email format (deve contenere `@` e un dominio) THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
8. WHEN `company` is provided AND exceeds 100 characters THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
9. WHEN `role` is provided AND its value is not one of `attendee`, `speaker`, `organizer` THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
10. IF `role` is absent from the request body THEN THE user-service SHALL default it to `attendee`.
11. IF `company` is absent from the request body THEN THE user-service SHALL store and return it as `null`.
12. THE user-service SHALL return all validation errors using the structure `{"error": {"code": "...", "message": "...", "details": {}}}` as defined in `platform-standards.md`.
13. WHEN `first_name` consists only of whitespace characters THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
14. WHEN `last_name` consists only of whitespace characters THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
15. WHEN `email` consists only of whitespace characters THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
16. THE user-service SHALL treat a whitespace-only value for any required string field as equivalent to an empty value: length checks SHALL be applied to the trimmed value, so that `"   "` is rejected exactly as `""` is.

_Nota (BUG-02): i criteri 13-16 sono stati aggiunti dopo aver rilevato che un `first_name` pari a `"   "` veniva accettato con `201`. Il criterio 2 parlava di campo "absent or empty" senza definire se una stringa di soli spazi contasse come vuota: la lacuna era nel requisito, non nel codice._

---

## REQ-USR-B01 — Unicità email (case-insensitive)

**User story:** As an organizer, I want the platform to prevent two accounts sharing the same email address so that user identity is unambiguous.

**Acceptance criteria**

1. WHEN a `POST /api/v1/users` request is received AND an existing user already has the same email (comparison is case-insensitive) THE user-service SHALL respond `409` with `error.code = "EMAIL_ALREADY_EXISTS"`.
2. WHEN a `PUT /api/v1/users/{id}` request is received AND the new email matches an existing user with a different `id` (comparison is case-insensitive) THE user-service SHALL respond `409` with `error.code = "EMAIL_ALREADY_EXISTS"`.
3. WHEN a `PATCH /api/v1/users/{id}` request includes an `email` field AND the new email matches an existing user with a different `id` (comparison is case-insensitive) THE user-service SHALL respond `409` with `error.code = "EMAIL_ALREADY_EXISTS"`.
4. IF the `PUT` or `PATCH` request sets the email to the same value already stored for that user (same `id`) THEN THE user-service SHALL NOT treat it as a conflict.

---

## REQ-USR-B02 — Normalizzazione email

**User story:** As a platform engineer, I want all emails stored in lowercase so that lookups and comparisons are always consistent.

**Acceptance criteria**

1. WHEN a user is created or updated with an email value THE user-service SHALL convert the email to lowercase before storing it.
2. THE user-service SHALL return the lowercase email in every response for that user.
3. IF a client sends `Ada@Example.COM` THEN THE user-service SHALL store and return `ada@example.com`.

---

## REQ-USR-B03 — Filtri sulla lista utenti

**User story:** As an event organizer, I want to filter the user list by role or email so that I can find specific users quickly.

**Acceptance criteria**

1. WHEN `GET /api/v1/users` is called with `?role=<value>` THE user-service SHALL return only users whose `role` equals the given value.
2. WHEN `GET /api/v1/users` is called with `?email=<value>` THE user-service SHALL return only users whose stored email equals the given value (comparison case-insensitive).
3. WHEN both `role` and `email` filters are present THE user-service SHALL apply both filters simultaneously (AND logic).
4. WHEN no filter is provided THE user-service SHALL return all users subject to pagination.
5. WHEN `role` filter value is not a valid role enum THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.

---

## REQ-USR-E01 — POST /api/v1/users — Creazione utente

**User story:** As a new conference attendee, I want to register my account so that I can access the platform features.

**Acceptance criteria**

1. WHEN a `POST /api/v1/users` request is received with a valid body THE user-service SHALL create the user, respond `201`, include the header `Location: /api/v1/users/<id>`, and return the full User object in the response body.
2. WHEN the user is created THE user-service SHALL generate a new UUID v4 as `id`.
3. WHEN the user is created THE user-service SHALL set both `created_at` and `updated_at` to the same UTC timestamp.
4. IF `role` is absent THEN THE user-service SHALL set it to `attendee` in the stored record and in the response.
5. WHEN the body is missing a required field (`first_name`, `last_name`, `email`) THE user-service SHALL respond `422` (see REQ-USR-F02).
6. WHEN the email is already taken THE user-service SHALL respond `409` (see REQ-USR-B01).
7. WHEN the JSON body is malformed THE user-service SHALL respond `400` (see REQ-USR-F02 criterion 1).

---

## REQ-USR-E02 — GET /api/v1/users — Lista paginata

**User story:** As an admin, I want to retrieve a paginated list of users so that I can browse large datasets without loading everything at once.

**Acceptance criteria**

1. WHEN `GET /api/v1/users` is called THE user-service SHALL respond `200` with body `{"items": [...], "page": <n>, "page_size": <n>, "total": <n>}`.
2. WHEN `?page=<n>&page_size=<m>` are provided THE user-service SHALL return the correct slice of results; `page` defaults to `1`, `page_size` defaults to `20`, maximum `100`.
3. WHEN `page_size` exceeds `100` THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
4. WHEN `page` is less than `1` THE user-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
5. WHEN the result set is empty THE user-service SHALL return `{"items": [], "page": 1, "page_size": 20, "total": 0}` with status `200`.

---

## REQ-USR-E03 — GET /api/v1/users/{id} — Lettura singolo utente

**User story:** As a service consumer (e.g. event-service), I want to fetch a single user by ID so that I can validate references and read user data.

**Acceptance criteria**

1. WHEN `GET /api/v1/users/{id}` is called AND the user exists THE user-service SHALL respond `200` with the full User object.
2. WHEN `GET /api/v1/users/{id}` is called AND no user with that `id` exists THE user-service SHALL respond `404` with `error.code = "NOT_FOUND"`.

---

## REQ-USR-E04 — PUT /api/v1/users/{id} — Sostituzione completa

**User story:** As a user, I want to replace all my profile data in a single operation so that I can update several fields at once atomically.

**Acceptance criteria**

1. WHEN `PUT /api/v1/users/{id}` is called with a valid body AND the user exists THE user-service SHALL replace all mutable fields (`first_name`, `last_name`, `email`, `company`, `role`), update `updated_at` to the current UTC timestamp, and respond `200` with the updated User object.
2. WHEN `PUT /api/v1/users/{id}` is called AND no user with that `id` exists THE user-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
3. WHEN the PUT body fails field validation THE user-service SHALL respond `422` (see REQ-USR-F02).
4. WHEN the new email conflicts with another user THE user-service SHALL respond `409` (see REQ-USR-B01).
5. THE user-service SHALL NOT change `id` or `created_at` during a PUT.
6. IF `role` is absent from the PUT body THEN THE user-service SHALL set it to `attendee` (same default as creation).

---

## REQ-USR-E05 — PATCH /api/v1/users/{id} — Aggiornamento parziale

**User story:** As a user, I want to update only specific fields of my profile so that I do not have to resend unchanged data.

**Acceptance criteria**

1. WHEN `PATCH /api/v1/users/{id}` is called with a valid partial body AND the user exists THE user-service SHALL update only the fields present in the request, set `updated_at` to the current UTC timestamp, and respond `200` with the full updated User object.
2. WHEN `PATCH /api/v1/users/{id}` is called AND no user with that `id` exists THE user-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
3. WHEN a field in the PATCH body fails validation THE user-service SHALL respond `422` (see REQ-USR-F02).
4. WHEN the PATCH body includes `email` AND it conflicts with another user THE user-service SHALL respond `409` (see REQ-USR-B01).
5. THE user-service SHALL NOT change `id` or `created_at` during a PATCH.
6. WHEN the PATCH body is empty (`{}`) THE user-service SHALL leave all fields unchanged, update `updated_at`, and respond `200`.

---

## REQ-USR-E06 — DELETE /api/v1/users/{id} — Cancellazione utente

**User story:** As an admin, I want to delete a user account so that stale records are removed from the platform.

**Acceptance criteria**

1. WHEN `DELETE /api/v1/users/{id}` is called AND the user exists THE user-service SHALL delete the user and respond `204` with no response body.
2. WHEN `DELETE /api/v1/users/{id}` is called AND no user with that `id` exists THE user-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
3. WHEN a user is deleted AND a subsequent `GET /api/v1/users/{id}` is made for the same `id` THE user-service SHALL respond `404`.

---

## REQ-USR-P01 — Persistenza multi-backend

**User story:** As a developer, I want the service to support three storage backends interchangeably so that I can run it in-memory during tests and on disk in production.

**Acceptance criteria**

1. WHEN `STORAGE_BACKEND=memory` (or the variable is unset) THE user-service SHALL store all data in a Python dictionary in-process; data is lost on restart.
2. WHEN `STORAGE_BACKEND=json` THE user-service SHALL persist data to a JSON file inside `DATA_DIR` (default `./data`); only the standard library `json` module SHALL be used.
3. WHEN `STORAGE_BACKEND=sqlite` THE user-service SHALL persist data to a SQLite file inside `DATA_DIR`; only the standard library `sqlite3` module SHALL be used.
4. WHEN the backend is switched THE user-service business logic (service.py) SHALL NOT require any modification; the repository interface SHALL be the only coupling point.
5. THE user-service SHALL create `DATA_DIR` automatically if it does not exist when `json` or `sqlite` backend is selected.

---

## REQ-USR-P02 — Configurazione e avvio

**User story:** As a platform operator, I want all runtime parameters to be read from environment variables so that the service can be configured without code changes.

**Acceptance criteria**

1. THE user-service SHALL read `PORT` from the environment and listen on `0.0.0.0:<PORT>`; default port is `5001`.
2. THE user-service SHALL read `STORAGE_BACKEND` from the environment; default is `memory`.
3. THE user-service SHALL read `DATA_DIR` from the environment; default is `./data`.
4. THE user-service SHALL be startable with the command `python -m app` executed from `services/user-service/`.
5. WHEN `PORT=15001` is set THE user-service SHALL listen on port `15001` (acceptance suite port) without any code change.

---

## REQ-USR-C01 — Conformità al contratto OpenAPI

**User story:** As a platform integrator, I want every response to conform to the OpenAPI contract so that downstream services and clients can rely on a stable schema.

**Acceptance criteria**

1. WHEN any endpoint returns a successful response THE user-service SHALL produce a body that validates against the corresponding schema in `contracts/openapi/user-service.yaml`.
2. WHEN any endpoint returns an error response THE user-service SHALL produce a body that matches the `Error` schema (`{"error": {"code": "...", "message": "...", "details": {...}}}`).
3. THE user-service SHALL NOT include additional top-level fields not defined in the contract (`additionalProperties: false`).
4. THE user-service SHALL return `Content-Type: application/json` for all non-204 responses.
