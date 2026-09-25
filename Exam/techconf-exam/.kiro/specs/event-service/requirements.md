# event-service — Requirements

Servizio: **event-service**
Base path: `/api/v1/events`
Porta di sviluppo: `5002`
Tipo: Obbligatorio
Contratto: `contracts/openapi/event-service.yaml`
Dipendenze: **user-service** (validazione `organizer_id`)

---

## REQ-EVT-00 — Health check

**User story:** As an operator, I want a health endpoint so that the acceptance harness can verify the service is up before sending traffic.

**Acceptance criteria**

1. WHEN a client sends `GET /health` THE event-service SHALL respond `200` with body `{"status": "ok", "service": "event-service"}`.
2. THE event-service SHALL respond to `GET /health` even when user-service is unreachable.

---

## REQ-EVT-F01 — Struttura della risorsa Event

**User story:** As an API consumer, I want every event to expose a stable set of fields so that I can rely on a consistent schema.

**Acceptance criteria**

1. THE event-service SHALL include in every Event response: `id`, `title`, `organizer_id`, `venue`, `city`, `start_date`, `end_date`, `capacity`, `price`, `status`, `created_at`, `updated_at`.
2. THE event-service SHALL generate `id` as UUID v4 server-side and SHALL NOT accept `id` in any request body.
3. THE event-service SHALL set `created_at` and `updated_at` to the current UTC timestamp in ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`) at creation.
4. THE event-service SHALL include `description` in the response; its value MAY be `null`.
5. THE event-service SHALL NOT include any field beyond those declared in `contracts/openapi/event-service.yaml` (`additionalProperties: false`).
6. THE event-service SHALL serialize `price` as a JSON number with 2 decimal places (e.g. `149.00`).
7. THE event-service SHALL serialize `start_date` and `end_date` as `YYYY-MM-DD` strings.

---

## REQ-EVT-F02 — Validazione dei campi in input

**User story:** As an API client, I want malformed payloads rejected with clear errors so that I can correct my request.

**Acceptance criteria**

1. WHEN the request body is not valid JSON THE event-service SHALL respond `400` with `error.code = "MALFORMED_JSON"`.
2. WHEN `title` is absent THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
3. WHEN `title` is shorter than 3 or longer than 120 characters THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
4. WHEN `description` is provided AND longer than 2000 characters THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
5. WHEN `organizer_id` is absent THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
6. WHEN `venue` is absent OR longer than 100 characters THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
7. WHEN `city` is absent OR longer than 60 characters THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
8. WHEN `start_date` is absent OR not in `YYYY-MM-DD` format THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
9. WHEN `end_date` is absent OR not in `YYYY-MM-DD` format THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
10. WHEN `capacity` is absent, not an integer, less than 1, or greater than 10000 THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
11. WHEN `price` is absent, not a number, or negative THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
12. WHEN `status` is provided AND is not one of `draft`, `published`, `cancelled` THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
13. IF `status` is absent from a creation request THEN THE event-service SHALL default it to `draft`.
14. IF `description` is absent THEN THE event-service SHALL store and return it as `null`.
15. THE event-service SHALL return every error using the structure `{"error": {"code": "...", "message": "...", "details": {...}}}` as defined in `platform-standards.md`.

---

## REQ-EVT-B01 — L'organizzatore deve esistere

**User story:** As a platform owner, I want every event to reference a real user as organizer, so that events are never orphaned.

**Acceptance criteria**

1. WHEN an event creation is requested THE event-service SHALL call `GET {USER_SERVICE_URL}/api/v1/users/{organizer_id}` to verify the organizer exists.
2. IF user-service responds `404` for the given `organizer_id` THEN THE event-service SHALL respond `422` with `error.code = "REFERENCE_NOT_FOUND"`.
3. WHEN a `PUT /api/v1/events/{id}` request is received THE event-service SHALL re-validate `organizer_id` with the same rule.
4. WHEN a `PATCH /api/v1/events/{id}` request includes `organizer_id` THE event-service SHALL re-validate it with the same rule.
5. IF a `PATCH` request does NOT include `organizer_id` THEN THE event-service SHALL NOT call user-service for organizer validation.

---

## REQ-EVT-B02 — L'organizzatore deve avere role = organizer

**User story:** As a platform owner, I want only users with the organizer role to own events, so that permissions are respected.

**Acceptance criteria**

1. WHEN user-service returns the organizer user AND `user.role != "organizer"` THE event-service SHALL respond `422` with `error.code = "INVALID_ORGANIZER"`.
2. WHEN user-service returns the organizer user AND `user.role == "organizer"` THE event-service SHALL proceed with the operation.
3. THE event-service SHALL apply this rule on creation (`POST`), full replacement (`PUT`), and on `PATCH` when `organizer_id` is present.
4. THE event-service SHALL distinguish this error from `REFERENCE_NOT_FOUND`: a user that exists but has the wrong role SHALL yield `INVALID_ORGANIZER`, not `REFERENCE_NOT_FOUND`.

---

## REQ-EVT-B03 — end_date non può precedere start_date

**User story:** As an organizer, I want the system to reject impossible date ranges so that event schedules are always coherent.

**Acceptance criteria**

1. WHEN an event is created or replaced AND `end_date` is earlier than `start_date` THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
2. WHEN `end_date` equals `start_date` THE event-service SHALL accept the request (single-day event).
3. WHEN a `PATCH` changes only `start_date` THE event-service SHALL validate the new `start_date` against the stored `end_date`.
4. WHEN a `PATCH` changes only `end_date` THE event-service SHALL validate the new `end_date` against the stored `start_date`.
5. WHEN a `PATCH` changes both dates THE event-service SHALL validate the two new values against each other.

---

## REQ-EVT-B04 — Transizioni di stato ammesse

**User story:** As an organizer, I want the event lifecycle enforced so that an event cannot go back to an earlier state.

**Acceptance criteria**

1. WHEN the current status is `draft` AND the requested status is `published` THE event-service SHALL apply the change and respond `200`.
2. WHEN the current status is `draft` AND the requested status is `cancelled` THE event-service SHALL apply the change and respond `200`.
3. WHEN the current status is `published` AND the requested status is `cancelled` THE event-service SHALL apply the change and respond `200`.
4. IF the current status is `published` AND the requested status is `draft` THEN THE event-service SHALL respond `422` with `error.code = "INVALID_STATUS_TRANSITION"`.
5. IF the current status is `cancelled` THEN THE event-service SHALL reject any status change with `422` and `error.code = "INVALID_STATUS_TRANSITION"` (terminal state).
6. WHEN the requested status equals the current status THE event-service SHALL accept the request as a no-op and respond `200`.
7. THE event-service SHALL apply these transition rules to both `PUT` and `PATCH`.

---

## REQ-EVT-B05 — user-service non raggiungibile

**User story:** As an operator, I want a clear 503 when a dependency is down so that failures are not mistaken for validation errors.

**Acceptance criteria**

1. WHEN the call to user-service times out after 2 seconds THE event-service SHALL respond `503` with `error.code = "DEPENDENCY_UNAVAILABLE"`.
2. WHEN the connection to user-service is refused THE event-service SHALL respond `503` with `error.code = "DEPENDENCY_UNAVAILABLE"`.
3. WHEN user-service responds with any `5xx` status THE event-service SHALL respond `503` with `error.code = "DEPENDENCY_UNAVAILABLE"`.
4. THE event-service SHALL use a fixed timeout of 2 seconds on every call to user-service.
5. THE event-service SHALL read the user-service base URL exclusively from the `USER_SERVICE_URL` environment variable, defaulting to `http://localhost:5001`.
6. THE event-service SHALL NOT contain any hard-coded user-service URL in its source code.

---

## REQ-EVT-B06 — Filtri sulla lista eventi

**User story:** As an attendee, I want to filter events by status and city so that I can find relevant conferences.

**Acceptance criteria**

1. WHEN `GET /api/v1/events` is called with `?status=<value>` THE event-service SHALL return only events whose `status` equals that value.
2. WHEN `GET /api/v1/events` is called with `?city=<value>` THE event-service SHALL return only events whose `city` equals that value.
3. WHEN both filters are present THE event-service SHALL apply both simultaneously (AND logic).
4. WHEN `status` is not a valid enum value THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
5. WHEN no filter is supplied THE event-service SHALL return all events subject to pagination.

---

## REQ-EVT-E01 — POST /api/v1/events — Creazione evento

**User story:** As an organizer, I want to create a conference so that attendees can later register for it.

**Acceptance criteria**

1. WHEN a valid creation request is received THE event-service SHALL create the event, respond `201`, include header `Location: /api/v1/events/<id>`, and return the full Event object.
2. WHEN the event is created THE event-service SHALL set `status` to `draft` unless a valid `status` was supplied.
3. WHEN the event is created THE event-service SHALL set `created_at` and `updated_at` to the same UTC timestamp.
4. WHEN field validation fails THE event-service SHALL respond `422` (see REQ-EVT-F02) **before** calling user-service.
5. WHEN the organizer does not exist THE event-service SHALL respond `422 REFERENCE_NOT_FOUND` (see REQ-EVT-B01).
6. WHEN the organizer has the wrong role THE event-service SHALL respond `422 INVALID_ORGANIZER` (see REQ-EVT-B02).
7. WHEN user-service is unreachable THE event-service SHALL respond `503 DEPENDENCY_UNAVAILABLE` (see REQ-EVT-B05).
8. WHEN the JSON body is malformed THE event-service SHALL respond `400 MALFORMED_JSON`.

---

## REQ-EVT-E02 — GET /api/v1/events — Lista paginata

**User story:** As an attendee, I want a paginated event list so that I can browse without loading everything.

**Acceptance criteria**

1. WHEN `GET /api/v1/events` is called THE event-service SHALL respond `200` with `{"items": [...], "page": n, "page_size": n, "total": n}`.
2. THE event-service SHALL default `page` to `1` and `page_size` to `20`, with `page_size` capped at `100`.
3. WHEN `page_size` exceeds `100` THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
4. WHEN `page` is less than `1` THE event-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
5. WHEN the result set is empty THE event-service SHALL respond `200` with `items` as an empty array and `total` equal to `0`.
6. THE event-service SHALL NOT call user-service when listing events.

---

## REQ-EVT-E03 — GET /api/v1/events/{id} — Lettura singolo evento

**User story:** As a service consumer (e.g. registration-service), I want to fetch a single event so that I can validate references and read capacity and price.

**Acceptance criteria**

1. WHEN the event exists THE event-service SHALL respond `200` with the full Event object.
2. WHEN no event with that `id` exists THE event-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
3. THE event-service SHALL NOT call user-service when reading a single event.

---

## REQ-EVT-E04 — PUT /api/v1/events/{id} — Sostituzione completa

**User story:** As an organizer, I want to replace all event data in one call so that I can apply several changes atomically.

**Acceptance criteria**

1. WHEN the event exists AND the body is valid THE event-service SHALL replace all mutable fields, update `updated_at`, and respond `200` with the updated Event.
2. WHEN no event with that `id` exists THE event-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
3. WHEN field validation fails THE event-service SHALL respond `422 VALIDATION_ERROR`.
4. WHEN the organizer reference is invalid THE event-service SHALL respond `422 REFERENCE_NOT_FOUND` or `422 INVALID_ORGANIZER` as applicable.
5. WHEN the requested `status` violates the transition rules THE event-service SHALL respond `422 INVALID_STATUS_TRANSITION`.
6. WHEN user-service is unreachable THE event-service SHALL respond `503 DEPENDENCY_UNAVAILABLE`.
7. THE event-service SHALL NOT change `id` or `created_at` during a `PUT`.
8. IF `status` is absent from the `PUT` body THEN THE event-service SHALL preserve the stored status.

---

## REQ-EVT-E05 — PATCH /api/v1/events/{id} — Aggiornamento parziale

**User story:** As an organizer, I want to update single fields so that I do not have to resend the whole event.

**Acceptance criteria**

1. WHEN the event exists AND the partial body is valid THE event-service SHALL update only the supplied fields, update `updated_at`, and respond `200` with the full Event.
2. WHEN no event with that `id` exists THE event-service SHALL respond `404 NOT_FOUND`.
3. WHEN a supplied field fails validation THE event-service SHALL respond `422 VALIDATION_ERROR`.
4. WHEN the body contains `status` THE event-service SHALL enforce the transition rules of REQ-EVT-B04.
5. WHEN the body contains `organizer_id` THE event-service SHALL re-validate it against user-service.
6. WHEN the body is empty (`{}`) THE event-service SHALL leave all fields unchanged, update `updated_at`, and respond `200`.
7. THE event-service SHALL NOT change `id` or `created_at` during a `PATCH`.

---

## REQ-EVT-E06 — DELETE /api/v1/events/{id} — Cancellazione evento

**User story:** As an organizer, I want to delete an event so that obsolete records are removed.

**Acceptance criteria**

1. WHEN the event exists THE event-service SHALL delete it and respond `204` with no body.
2. WHEN no event with that `id` exists THE event-service SHALL respond `404 NOT_FOUND`.
3. WHEN an event has been deleted AND a subsequent `GET` is made for the same `id` THE event-service SHALL respond `404`.
4. THE event-service SHALL NOT call user-service when deleting an event.

---

## REQ-EVT-P01 — Persistenza multi-backend

**User story:** As a developer, I want three interchangeable storage backends so that tests run in memory and deployments can persist to disk.

**Acceptance criteria**

1. WHEN `STORAGE_BACKEND=memory` (or unset) THE event-service SHALL keep all data in an in-process dictionary.
2. WHEN `STORAGE_BACKEND=json` THE event-service SHALL persist to a JSON file inside `DATA_DIR`, using only the standard-library `json` module.
3. WHEN `STORAGE_BACKEND=sqlite` THE event-service SHALL persist to a SQLite file inside `DATA_DIR`, using only the standard-library `sqlite3` module.
4. WHEN the backend changes THE event-service business logic SHALL require no modification; the repository interface SHALL be the only coupling point.
5. THE event-service SHALL create `DATA_DIR` automatically when the `json` or `sqlite` backend is selected.

---

## REQ-EVT-P02 — Configurazione e avvio

**User story:** As an operator, I want all runtime parameters supplied via environment variables so that no code change is needed to deploy.

**Acceptance criteria**

1. THE event-service SHALL read `PORT` from the environment and listen on `0.0.0.0:<PORT>`, defaulting to `5002`.
2. THE event-service SHALL read `USER_SERVICE_URL` from the environment, defaulting to `http://localhost:5001`.
3. THE event-service SHALL read `STORAGE_BACKEND` from the environment, defaulting to `memory`.
4. THE event-service SHALL read `DATA_DIR` from the environment, defaulting to `./data`.
5. THE event-service SHALL be startable with `python -m app` executed from `services/event-service/`.
6. WHEN `PORT=15002` is set THE event-service SHALL listen on port `15002` without any code change.

---

## REQ-EVT-C01 — Conformità al contratto OpenAPI

**User story:** As a platform integrator, I want every response to match the contract so that clients and downstream services can rely on it.

**Acceptance criteria**

1. WHEN any endpoint returns a successful response THE event-service SHALL produce a body validating against the matching schema in `contracts/openapi/event-service.yaml`.
2. WHEN any endpoint returns an error THE event-service SHALL produce a body matching the `Error` schema.
3. THE event-service SHALL NOT add fields absent from the contract (`additionalProperties: false`).
4. THE event-service SHALL return `Content-Type: application/json` for every response except `204`.
