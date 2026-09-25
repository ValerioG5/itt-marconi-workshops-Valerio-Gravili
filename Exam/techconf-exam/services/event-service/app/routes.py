import re

from flask import jsonify, request

from app.repository.base import (
    DependencyUnavailableError,
    EventNotFoundError,
    InvalidOrganizerError,
    InvalidStatusTransitionError,
    OrganizerNotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = {"draft", "published", "cancelled"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EVENT_FIELDS = ("id", "title", "description", "organizer_id", "venue", "city",
                 "start_date", "end_date", "capacity", "price", "status",
                 "created_at", "updated_at")

# Eccezioni di dominio che le route di scrittura sanno tradurre in HTTP.
_DOMAIN_ERRORS = (
    OrganizerNotFoundError,
    InvalidOrganizerError,
    InvalidStatusTransitionError,
    ValidationError,
    DependencyUnavailableError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(code, message, status, details=None):
    """Costruisce una risposta di errore standard (platform-standards.md)."""
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    return jsonify(body), status


def _validate_event_input(data: dict, partial: bool = False) -> list:
    """Valida i campi in input (REQ-EVT-F02); restituisce la lista di errori.

    Con `partial=True` (PATCH) i campi assenti sono ammessi: si valida solo
    ciò che è stato effettivamente fornito.
    """
    errors = []

    # title — 3..120 caratteri (sul valore trimmed, BUG-02)
    if "title" in data:
        v = data["title"]
        if not isinstance(v, str) or not (3 <= len(v.strip()) <= 120):
            errors.append("title must be a string of 3–120 characters.")
    elif not partial:
        errors.append("title is required.")

    # description — opzionale e nullable, max 2000 caratteri
    if "description" in data and data["description"] is not None:
        v = data["description"]
        if not isinstance(v, str) or len(v) > 2000:
            errors.append("description must be a string of at most 2000 characters.")

    # organizer_id — stringa non vuota
    if "organizer_id" in data:
        v = data["organizer_id"]
        if not isinstance(v, str) or not v:
            errors.append("organizer_id must be a non-empty string.")
    elif not partial:
        errors.append("organizer_id is required.")

    # venue — 1..100 caratteri (sul valore trimmed, BUG-02)
    if "venue" in data:
        v = data["venue"]
        if not isinstance(v, str) or not (1 <= len(v.strip()) <= 100):
            errors.append("venue must be a string of 1–100 characters.")
    elif not partial:
        errors.append("venue is required.")

    # city — 1..60 caratteri (sul valore trimmed, BUG-02)
    if "city" in data:
        v = data["city"]
        if not isinstance(v, str) or not (1 <= len(v.strip()) <= 60):
            errors.append("city must be a string of 1–60 characters.")
    elif not partial:
        errors.append("city is required.")

    # start_date / end_date — formato YYYY-MM-DD
    for field in ("start_date", "end_date"):
        if field in data:
            v = data[field]
            if not isinstance(v, str) or not _DATE_RE.match(v):
                errors.append(f"{field} must be a date in YYYY-MM-DD format.")
        elif not partial:
            errors.append(f"{field} is required.")

    # capacity — intero 1..10000 (bool è sottoclasse di int: va escluso)
    if "capacity" in data:
        v = data["capacity"]
        if isinstance(v, bool) or not isinstance(v, int) or not (1 <= v <= 10000):
            errors.append("capacity must be an integer between 1 and 10000.")
    elif not partial:
        errors.append("capacity is required.")

    # price — numero >= 0
    if "price" in data:
        v = data["price"]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            errors.append("price must be a number greater than or equal to 0.")
    elif not partial:
        errors.append("price is required.")

    # status — enum
    if "status" in data and data["status"] not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}.")

    return errors


def _serialize_event(event: dict) -> dict:
    """Espone solo i campi dichiarati nel contratto (additionalProperties: false)."""
    return {
        "id": event["id"],
        "title": event["title"],
        "description": event.get("description"),
        "organizer_id": event["organizer_id"],
        "venue": event["venue"],
        "city": event["city"],
        "start_date": event["start_date"],
        "end_date": event["end_date"],
        "capacity": int(event["capacity"]),
        "price": round(float(event["price"]), 2),
        "status": event["status"],
        "created_at": event["created_at"],
        "updated_at": event["updated_at"],
    }


def _paginate(page_items: list, page: int, page_size: int, total: int) -> dict:
    """Costruisce il body paginato serializzando ogni evento."""
    return {
        "items": [_serialize_event(e) for e in page_items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _map_domain_error(exc):
    """Traduce un'eccezione di dominio nella risposta HTTP corrispondente.

    Centralizzato perché POST, PUT e PATCH condividono la stessa mappatura.
    """
    if isinstance(exc, OrganizerNotFoundError):
        return _error_response("REFERENCE_NOT_FOUND", "Referenced organizer does not exist.", 422)
    if isinstance(exc, InvalidOrganizerError):
        return _error_response("INVALID_ORGANIZER", "Referenced user is not an organizer.", 422)
    if isinstance(exc, InvalidStatusTransitionError):
        return _error_response("INVALID_STATUS_TRANSITION", f"Invalid status transition: {exc}", 422)
    if isinstance(exc, ValidationError):
        return _error_response("VALIDATION_ERROR", str(exc), 422)
    if isinstance(exc, DependencyUnavailableError):
        return _error_response("DEPENDENCY_UNAVAILABLE", "A dependency is unavailable.", 503)
    raise exc   # non gestita: rilancia


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------

def register_routes(app, service):
    """Registra tutte le route dell'app Flask."""

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "event-service"}), 200

    @app.errorhandler(400)
    def handle_bad_request(e):
        return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

    # ------------------------------------------------------------------
    # POST /api/v1/events — Creazione evento  (REQ-EVT-E01)
    # ------------------------------------------------------------------

    @app.route("/api/v1/events", methods=["POST"])
    def create_event():
        # silent=False: un JSON malformato produce un 400 gestito dall'errorhandler
        data = request.get_json(force=True, silent=False)
        if data is None:
            return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

        # REQ-EVT-E01 criterio 4: la validazione dei campi precede
        # qualunque chiamata a user-service.
        errors = _validate_event_input(data, partial=False)
        if errors:
            return _error_response("VALIDATION_ERROR", "; ".join(errors), 422)

        try:
            event = service.create_event(data)
        except _DOMAIN_ERRORS as exc:
            return _map_domain_error(exc)

        resp = jsonify(_serialize_event(event))
        resp.status_code = 201
        resp.headers["Location"] = f"/api/v1/events/{event['id']}"
        return resp

    # ------------------------------------------------------------------
    # GET /api/v1/events — Lista paginata  (REQ-EVT-E02, REQ-EVT-B06)
    # ------------------------------------------------------------------

    @app.route("/api/v1/events", methods=["GET"])
    def list_events():
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 20))
        except ValueError:
            return _error_response("VALIDATION_ERROR", "page and page_size must be integers.", 422)

        if page < 1:
            return _error_response("VALIDATION_ERROR", "page must be >= 1.", 422)
        if not (1 <= page_size <= 100):
            return _error_response("VALIDATION_ERROR", "page_size must be between 1 and 100.", 422)

        status = request.args.get("status")
        city = request.args.get("city")

        # REQ-EVT-B06 criterio 4
        if status is not None and status not in VALID_STATUSES:
            return _error_response(
                "VALIDATION_ERROR",
                f"status must be one of {sorted(VALID_STATUSES)}.",
                422,
            )

        items, total = service.list_events(status, city, page, page_size)
        return jsonify(_paginate(items, page, page_size, total)), 200

    # ------------------------------------------------------------------
    # GET /api/v1/events/<event_id> — Lettura singolo evento  (REQ-EVT-E03)
    # ------------------------------------------------------------------

    @app.route("/api/v1/events/<event_id>", methods=["GET"])
    def get_event(event_id):
        try:
            event = service.get_event(event_id)
        except EventNotFoundError:
            return _error_response("NOT_FOUND", f"Event '{event_id}' not found.", 404)
        return jsonify(_serialize_event(event)), 200

    # ------------------------------------------------------------------
    # PUT /api/v1/events/<event_id> — Sostituzione completa  (REQ-EVT-E04)
    # ------------------------------------------------------------------

    @app.route("/api/v1/events/<event_id>", methods=["PUT"])
    def replace_event(event_id):
        data = request.get_json(force=True, silent=False)
        if data is None:
            return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

        errors = _validate_event_input(data, partial=False)
        if errors:
            return _error_response("VALIDATION_ERROR", "; ".join(errors), 422)

        try:
            event = service.replace_event(event_id, data)
        except EventNotFoundError:
            return _error_response("NOT_FOUND", f"Event '{event_id}' not found.", 404)
        except _DOMAIN_ERRORS as exc:
            return _map_domain_error(exc)

        return jsonify(_serialize_event(event)), 200

    # ------------------------------------------------------------------
    # PATCH /api/v1/events/<event_id> — Aggiornamento parziale  (REQ-EVT-E05)
    # ------------------------------------------------------------------

    @app.route("/api/v1/events/<event_id>", methods=["PATCH"])
    def update_event(event_id):
        data = request.get_json(force=True, silent=False)
        if data is None:
            return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

        errors = _validate_event_input(data, partial=True)
        if errors:
            return _error_response("VALIDATION_ERROR", "; ".join(errors), 422)

        try:
            event = service.update_event(event_id, data)
        except EventNotFoundError:
            return _error_response("NOT_FOUND", f"Event '{event_id}' not found.", 404)
        except _DOMAIN_ERRORS as exc:
            return _map_domain_error(exc)

        return jsonify(_serialize_event(event)), 200

    # ------------------------------------------------------------------
    # DELETE /api/v1/events/<event_id> — Cancellazione evento  (REQ-EVT-E06)
    # ------------------------------------------------------------------

    @app.route("/api/v1/events/<event_id>", methods=["DELETE"])
    def delete_event(event_id):
        try:
            service.delete_event(event_id)
        except EventNotFoundError:
            return _error_response("NOT_FOUND", f"Event '{event_id}' not found.", 404)
        return "", 204
