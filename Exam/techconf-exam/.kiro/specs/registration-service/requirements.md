# registration-service — Requirements

Servizio: **registration-service**
Base path: `/api/v1/registrations`
Porta di sviluppo: `5003`
Tipo: Obbligatorio
Contratto: `contracts/openapi/registration-service.yaml`
Dipendenze: **user-service** (validazione `user_id`), **event-service** (validazione `event_id`, lettura `price` e `capacity`)

---

## REQ-REG-00 — Health check

**User story:** As an operator, I want a health endpoint so that the acceptance harness can verify the service is up before sending traffic.

**Acceptance criteria**

1. WHEN a client sends `GET /health` THE registration-service SHALL respond `200` with body `{"status": "ok", "service": "registration-service"}`.
2. THE registration-service SHALL respond to `GET /health` even when user-service or event-service are unreachable.

---

## REQ-REG-F01 — Struttura della risorsa Registration

**User story:** As an API consumer, I want every registration to expose a stable set of fields so that I can rely on a consistent schema.

**Acceptance criteria**

1. THE registration-service SHALL include in every Registration response: `id`, `user_id`, `event_id`, `amount`, `status`, `created_at`, `updated_at`.
2. THE registration-service SHALL generate `id` as UUID v4 server-side and SHALL NOT accept `id` in any request body.
3. THE registration-service SHALL set `created_at` and `updated_at` to the current UTC timestamp in ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`) at creation.
4. THE registration-service SHALL NOT include any field beyond those declared in the contract (`additionalProperties: false`).
5. THE registration-service SHALL serialize `amount` as a JSON number with 2 decimal places.

---

## REQ-REG-F02 — Validazione dei campi in input

**User story:** As an API client, I want malformed payloads rejected with clear errors so that I can correct my request.

**Acceptance criteria**

1. WHEN the request body is not valid JSON THE registration-service SHALL respond `400` with `error.code = "MALFORMED_JSON"`.
2. WHEN `user_id` is absent or is not a non-empty string THE registration-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
3. WHEN `event_id` is absent or is not a non-empty string THE registration-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
4. WHEN the creation body contains `amount` THE registration-service SHALL ignore it: `amount` is read-only and derived from the event price (see REQ-REG-B06).
5. WHEN the creation body contains `status` THE registration-service SHALL ignore it: every new registration starts as `confirmed`.
6. THE registration-service SHALL perform field validation **before** calling any dependency.
7. THE registration-service SHALL return every error using the structure `{"error": {"code": "...", "message": "...", "details": {...}}}`.

---

## REQ-REG-B01 — L'utente deve esistere

**User story:** As a platform owner, I want every registration to reference a real user so that registrations are never orphaned.

**Acceptance criteria**

1. WHEN a registration is requested THE registration-service SHALL call `GET {USER_SERVICE_URL}/api/v1/users/{user_id}` to verify the user exists.
2. IF user-service responds `404` for the given `user_id` THEN THE registration-service SHALL respond `422` with `error.code = "REFERENCE_NOT_FOUND"`.
3. WHEN the user exists THE registration-service SHALL proceed to validate the event.
4. THE registration-service SHALL NOT impose any constraint on the user's `role`: attendees, speakers and organizers may all register.

---

## REQ-REG-B02 — L'evento deve esistere

**User story:** As a platform owner, I want every registration to reference a real event so that capacity accounting is meaningful.

**Acceptance criteria**

1. WHEN a registration is requested THE registration-service SHALL call `GET {EVENT_SERVICE_URL}/api/v1/events/{event_id}` to verify the event exists.
2. IF event-service responds `404` for the given `event_id` THEN THE registration-service SHALL respond `422` with `error.code = "REFERENCE_NOT_FOUND"`.
3. WHEN the event exists THE registration-service SHALL read its `status`, `price` and `capacity` from the response.

---

## REQ-REG-B03 — L'evento deve essere published

**User story:** As an organizer, I want registrations accepted only for published events so that drafts and cancelled events cannot be booked.

**Acceptance criteria**

1. IF the referenced event has `status != "published"` THEN THE registration-service SHALL respond `422` with `error.code = "EVENT_NOT_OPEN"`.
2. WHEN the event has `status == "draft"` THE registration-service SHALL respond `422 EVENT_NOT_OPEN`.
3. WHEN the event has `status == "cancelled"` THE registration-service SHALL respond `422 EVENT_NOT_OPEN`.
4. THE registration-service SHALL distinguish this error from `REFERENCE_NOT_FOUND`: an event that exists but is not published SHALL yield `EVENT_NOT_OPEN`.

---

## REQ-REG-B04 — Nessuna doppia iscrizione confermata

**User story:** As an organizer, I want to prevent the same user from holding two confirmed seats for one event, so that seat accounting is fair and accurate.

**Acceptance criteria**

1. IF a registration with the same `(user_id, event_id)` pair already exists AND its `status` is `confirmed` THEN THE registration-service SHALL respond `409` with `error.code = "ALREADY_REGISTERED"`.
2. WHEN the only existing registration for the same `(user_id, event_id)` pair has `status == "cancelled"` THE registration-service SHALL allow the new registration and create a new record with `status = "confirmed"`.
3. THE registration-service SHALL evaluate this rule **only** against registrations whose status is `confirmed`; `cancelled` registrations SHALL NOT block a new one.
4. THE registration-service SHALL evaluate this check after validating user and event references, and before the capacity check.
5. WHEN a different user registers for the same event THE registration-service SHALL NOT treat it as a duplicate.
6. WHEN the same user registers for a different event THE registration-service SHALL NOT treat it as a duplicate.

---

## REQ-REG-B05 — Capienza dell'evento

**User story:** As an organizer, I want registrations to stop when the event is full, so that we never exceed the venue capacity.

**Acceptance criteria**

1. WHEN a registration is requested AND the number of `confirmed` registrations for the event is fewer than `event.capacity` THE registration-service SHALL create it with `status = "confirmed"`.
2. IF the number of `confirmed` registrations for the event is greater than or equal to `event.capacity` THEN THE registration-service SHALL respond `409` with `error.code = "EVENT_FULL"`.
3. THE registration-service SHALL count **only** registrations with `status == "confirmed"` when evaluating occupancy; `cancelled` registrations SHALL NOT count towards the capacity.
4. WHEN a confirmed registration is cancelled THE registration-service SHALL free one seat, making a subsequent registration possible (see REQ-REG-B07).
5. THE registration-service SHALL read `capacity` from the event-service response for the specific `event_id`, never from the client payload.
6. THE registration-service SHALL perform the capacity check immediately before persisting the new registration, so that the counted occupancy and the write are not separated by any other dependency call.
7. WHEN an event has `capacity = 1` AND one confirmed registration exists THE registration-service SHALL reject a second registration with `409 EVENT_FULL`.

---

## REQ-REG-B06 — amount copiato da event.price

**User story:** As a finance stakeholder, I want the registration amount to come from the event price at booking time, so that clients cannot choose what they pay.

**Acceptance criteria**

1. WHEN a registration is created THE registration-service SHALL set `amount` to the `price` value returned by event-service for that `event_id`.
2. THE registration-service SHALL ignore any `amount` supplied in the request body.
3. WHEN the event price is `149.00` THE registration-service SHALL store and return `amount` equal to `149.00`.
4. WHEN the event price is `0` THE registration-service SHALL store and return `amount` equal to `0.00`.
5. THE registration-service SHALL NOT recalculate or update `amount` when the event price changes after the registration was created.

---

## REQ-REG-B07 — Transizione confirmed → cancelled

**User story:** As an attendee, I want to cancel my registration so that I release my seat for someone else.

**Acceptance criteria**

1. WHEN the current status is `confirmed` AND the requested status is `cancelled` THE registration-service SHALL apply the change and respond `200`.
2. IF the current status is `cancelled` AND the requested status is `confirmed` THEN THE registration-service SHALL respond `422` with `error.code = "INVALID_STATUS_TRANSITION"`.
3. WHEN a registration is cancelled THE registration-service SHALL decrease the confirmed count for that event by one, freeing a seat.
4. WHEN the requested status equals the current status THE registration-service SHALL accept the request as a no-op and respond `200`.
5. WHEN a `PATCH` body contains a `status` value outside `{confirmed, cancelled}` THE registration-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
6. WHEN a `PATCH` body does not contain `status` THE registration-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"` (the contract marks `status` as required in `RegistrationPatch`).
7. THE registration-service SHALL NOT call user-service or event-service when handling a `PATCH`.

---

## REQ-REG-B08 — Endpoint stats

**User story:** As an organizer, I want live occupancy figures for my event so that I can see how many seats are left.

**Acceptance criteria**

1. WHEN `GET /api/v1/registrations/stats?event_id=<id>` is called for an existing event THE registration-service SHALL respond `200` with body `{"event_id": <id>, "capacity": <n>, "confirmed": <n>, "available": <n>}`.
2. THE registration-service SHALL compute `confirmed` as the number of registrations for that `event_id` whose status is `confirmed`.
3. THE registration-service SHALL compute `available` as `capacity - confirmed`.
4. THE registration-service SHALL clamp `available` at a minimum of `0`, so that it is never negative.
5. IF the referenced event does not exist THEN THE registration-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
6. WHEN the `event_id` query parameter is absent THE registration-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
7. WHEN event-service is unreachable THE registration-service SHALL respond `503` with `error.code = "DEPENDENCY_UNAVAILABLE"`.
8. THE registration-service SHALL route `/api/v1/registrations/stats` so that the literal segment `stats` is never interpreted as a registration `id`.

---

## REQ-REG-B09 — Dipendenza non raggiungibile

**User story:** As an operator, I want a clear 503 when a dependency is down so that failures are not mistaken for validation errors.

**Acceptance criteria**

1. WHEN a call to user-service or event-service times out after 2 seconds THE registration-service SHALL respond `503` with `error.code = "DEPENDENCY_UNAVAILABLE"`.
2. WHEN the connection to user-service or event-service is refused THE registration-service SHALL respond `503` with `error.code = "DEPENDENCY_UNAVAILABLE"`.
3. WHEN user-service or event-service respond with any `5xx` status THE registration-service SHALL respond `503` with `error.code = "DEPENDENCY_UNAVAILABLE"`.
4. THE registration-service SHALL use a fixed timeout of 2 seconds on every outbound call.
5. THE registration-service SHALL read dependency base URLs exclusively from the `USER_SERVICE_URL` and `EVENT_SERVICE_URL` environment variables, defaulting to `http://localhost:5001` and `http://localhost:5002`.
6. THE registration-service SHALL NOT contain any hard-coded dependency URL in its source code.

---

## REQ-REG-E01 — POST /api/v1/registrations — Creazione iscrizione

**User story:** As an attendee, I want to register for a published conference so that I secure a seat.

**Acceptance criteria**

1. WHEN a valid creation request is received THE registration-service SHALL create the registration, respond `201`, include header `Location: /api/v1/registrations/<id>`, and return the full Registration object.
2. WHEN the registration is created THE registration-service SHALL set `status` to `confirmed`.
3. WHEN the registration is created THE registration-service SHALL set `created_at` and `updated_at` to the same UTC timestamp.
4. THE registration-service SHALL perform its checks in this order: field validation, user existence, event existence, event published, duplicate registration, capacity.
5. WHEN the JSON body is malformed THE registration-service SHALL respond `400 MALFORMED_JSON`.

---

## REQ-REG-E02 — GET /api/v1/registrations — Lista paginata con filtri

**User story:** As an organizer, I want to filter registrations by user, event and status so that I can inspect bookings.

**Acceptance criteria**

1. WHEN `GET /api/v1/registrations` is called THE registration-service SHALL respond `200` with `{"items": [...], "page": n, "page_size": n, "total": n}`.
2. THE registration-service SHALL default `page` to `1` and `page_size` to `20`, with `page_size` capped at `100`.
3. WHEN `page_size` exceeds `100` OR `page` is less than `1` THE registration-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
4. WHEN `?user_id=<id>` is supplied THE registration-service SHALL return only registrations for that user.
5. WHEN `?event_id=<id>` is supplied THE registration-service SHALL return only registrations for that event.
6. WHEN `?status=<value>` is supplied THE registration-service SHALL return only registrations with that status.
7. WHEN several filters are supplied THE registration-service SHALL apply them simultaneously (AND logic).
8. WHEN `status` is not one of `confirmed`, `cancelled` THE registration-service SHALL respond `422` with `error.code = "VALIDATION_ERROR"`.
9. THE registration-service SHALL NOT call any dependency when listing registrations.

---

## REQ-REG-E03 — GET /api/v1/registrations/{id} — Lettura singola

**User story:** As an API consumer, I want to fetch a single registration so that I can confirm its status and amount.

**Acceptance criteria**

1. WHEN the registration exists THE registration-service SHALL respond `200` with the full Registration object.
2. WHEN no registration with that `id` exists THE registration-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
3. THE registration-service SHALL NOT call any dependency when reading a single registration.

---

## REQ-REG-E04 — PATCH /api/v1/registrations/{id} — Solo status

**User story:** As an attendee, I want to cancel my registration through a partial update so that I do not have to resend other fields.

**Acceptance criteria**

1. WHEN the registration exists AND the body contains a valid `status` THE registration-service SHALL apply the transition rules of REQ-REG-B07, update `updated_at`, and respond `200`.
2. WHEN no registration with that `id` exists THE registration-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
3. THE registration-service SHALL ignore any field other than `status` in the `PATCH` body.
4. THE registration-service SHALL NOT allow `user_id`, `event_id` or `amount` to be modified.

---

## REQ-REG-E05 — DELETE /api/v1/registrations/{id} — Cancellazione

**User story:** As an admin, I want to delete a registration record so that erroneous bookings can be removed.

**Acceptance criteria**

1. WHEN the registration exists THE registration-service SHALL delete it and respond `204` with no body.
2. WHEN no registration with that `id` exists THE registration-service SHALL respond `404` with `error.code = "NOT_FOUND"`.
3. WHEN a registration has been deleted THE registration-service SHALL no longer count it towards the event occupancy.

---

## REQ-REG-E06 — PUT /api/v1/registrations/{id} — Non previsto

**User story:** As an API consumer, I want unsupported methods to fail predictably so that I do not rely on undefined behaviour.

**Acceptance criteria**

1. WHEN `PUT /api/v1/registrations/{id}` is called THE registration-service SHALL respond `405`.
2. THE registration-service SHALL return a body matching the `Error` schema for the `405` response.
3. THE registration-service SHALL NOT create or modify any registration in response to a `PUT`.

---

## REQ-REG-P01 — Persistenza multi-backend

**User story:** As a developer, I want three interchangeable storage backends so that tests run in memory and deployments can persist to disk.

**Acceptance criteria**

1. WHEN `STORAGE_BACKEND=memory` (or unset) THE registration-service SHALL keep all data in an in-process dictionary.
2. WHEN `STORAGE_BACKEND=json` THE registration-service SHALL persist to a JSON file inside `DATA_DIR`, using only the standard-library `json` module.
3. WHEN `STORAGE_BACKEND=sqlite` THE registration-service SHALL persist to a SQLite file inside `DATA_DIR`, using only the standard-library `sqlite3` module.
4. WHEN the backend changes THE registration-service business logic SHALL require no modification.
5. THE registration-service SHALL create `DATA_DIR` automatically when the `json` or `sqlite` backend is selected.
6. THE repository interface SHALL expose a dedicated operation to count `confirmed` registrations for an `event_id`, so that the capacity rule does not depend on loading every record.

---

## REQ-REG-P02 — Configurazione e avvio

**User story:** As an operator, I want all runtime parameters supplied via environment variables so that no code change is needed to deploy.

**Acceptance criteria**

1. THE registration-service SHALL read `PORT` from the environment and listen on `0.0.0.0:<PORT>`, defaulting to `5003`.
2. THE registration-service SHALL read `USER_SERVICE_URL` from the environment, defaulting to `http://localhost:5001`.
3. THE registration-service SHALL read `EVENT_SERVICE_URL` from the environment, defaulting to `http://localhost:5002`.
4. THE registration-service SHALL read `STORAGE_BACKEND` and `DATA_DIR` from the environment, defaulting to `memory` and `./data`.
5. THE registration-service SHALL be startable with `python -m app` executed from `services/registration-service/`.
6. WHEN `PORT=15003` is set THE registration-service SHALL listen on port `15003` without any code change.

---

## REQ-REG-C01 — Conformità al contratto OpenAPI

**User story:** As a platform integrator, I want every response to match the contract so that clients and downstream services can rely on it.

**Acceptance criteria**

1. WHEN any endpoint returns a successful response THE registration-service SHALL produce a body validating against the matching schema in `contracts/openapi/registration-service.yaml`.
2. WHEN any endpoint returns an error THE registration-service SHALL produce a body matching the `Error` schema.
3. THE registration-service SHALL NOT add fields absent from the contract (`additionalProperties: false`).
4. THE registration-service SHALL return `Content-Type: application/json` for every response except `204`.
