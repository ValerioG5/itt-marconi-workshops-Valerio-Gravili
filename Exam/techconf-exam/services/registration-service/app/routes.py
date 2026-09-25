from flask import jsonify, request

from app.repository.base import (
    AlreadyRegisteredError,
    DependencyUnavailableError,
    EventFullError,
    EventNotFoundForStatsError,
    EventNotOpenError,
    InvalidStatusTransitionError,
    ReferenceNotFoundError,
    RegistrationNotFoundError,
    ValidationError,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = {"confirmed", "cancelled"}

# Eccezioni di dominio che le route sanno tradurre in HTTP (design §4.3).
_DOMAIN_ERRORS = (
    ReferenceNotFoundError,
    EventNotOpenError,
    AlreadyRegisteredError,
    EventFullError,
    InvalidStatusTransitionError,
    ValidationError,
    DependencyUnavailableError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_response(code, message, status, details=None):
    """Costruisce il corpo conforme allo schema `Error` del contratto."""
    body = {"error": {"code": code, "message": message, "details": details or {}}}
    return jsonify(body), status


def _validate_create_input(data: dict) -> list:
    """REQ-REG-F02. `amount` e `status` nel payload sono ignorati (read-only)."""
    errors = []
    for field in ("user_id", "event_id"):
        if field in data:
            v = data[field]
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{field} must be a non-empty string.")
        else:
            errors.append(f"{field} is required.")
    return errors


def _validate_patch_input(data: dict) -> list:
    """RegistrationPatch dichiara `status` come required."""
    errors = []
    if "status" not in data:
        errors.append("status is required.")
    elif data["status"] not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}.")
    return errors


def _serialize_registration(reg: dict) -> dict:
    """Solo i 7 campi del contratto (additionalProperties: false)."""
    return {
        "id": reg["id"],
        "user_id": reg["user_id"],
        "event_id": reg["event_id"],
        "amount": round(float(reg["amount"]), 2),
        "status": reg["status"],
        "created_at": reg["created_at"],
        "updated_at": reg["updated_at"],
    }


def _paginate(page_items, page, page_size, total):
    return {
        "items": [_serialize_registration(r) for r in page_items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


def _map_domain_error(exc):
    """design §4.3. AlreadyRegistered e EventFull sono entrambe 409 ma con codici distinti."""
    if isinstance(exc, ReferenceNotFoundError):
        return _error_response("REFERENCE_NOT_FOUND", "Referenced resource does not exist.", 422)
    if isinstance(exc, EventNotOpenError):
        return _error_response("EVENT_NOT_OPEN", "Event is not open for registration.", 422)
    if isinstance(exc, AlreadyRegisteredError):
        return _error_response("ALREADY_REGISTERED", "User is already registered to this event.", 409)
    if isinstance(exc, EventFullError):
        return _error_response("EVENT_FULL", "Event has reached its capacity.", 409)
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
    # Health e handler di errore
    # ------------------------------------------------------------------

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "registration-service"}), 200

    @app.errorhandler(400)
    def handle_bad_request(e):
        return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

    @app.errorhandler(405)
    def handle_method_not_allowed(e):
        # Il default HTML di Werkzeug non rispetta lo schema `Error` richiesto
        # dal contratto per il PUT su /api/v1/registrations/{id}.
        return _error_response(
            "METHOD_NOT_ALLOWED", "Method not allowed for this resource.", 405
        )

    # ------------------------------------------------------------------
    # POST /api/v1/registrations — Creazione registrazione  (REQ-REG-E01)
    # ------------------------------------------------------------------

    @app.route("/api/v1/registrations", methods=["POST"])
    def create_registration():
        # silent=False: un JSON malformato produce un 400 gestito dall'errorhandler
        data = request.get_json(force=True, silent=False)
        if data is None:
            return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

        # REQ-REG-F02 criterio 6: la validazione precede qualunque chiamata
        # alle dipendenze HTTP.
        errors = _validate_create_input(data)
        if errors:
            return _error_response("VALIDATION_ERROR", "; ".join(errors), 422)

        try:
            registration = service.create_registration(data)
        except _DOMAIN_ERRORS as exc:
            return _map_domain_error(exc)

        resp = jsonify(_serialize_registration(registration))
        resp.status_code = 201
        resp.headers["Location"] = f"/api/v1/registrations/{registration['id']}"
        return resp

    # ------------------------------------------------------------------
    # GET /api/v1/registrations — Lista paginata  (REQ-REG-E02)
    # ------------------------------------------------------------------

    @app.route("/api/v1/registrations", methods=["GET"])
    def list_registrations():
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 20))
        except ValueError:
            return _error_response("VALIDATION_ERROR", "page and page_size must be integers.", 422)

        if page < 1:
            return _error_response("VALIDATION_ERROR", "page must be >= 1.", 422)
        if not (1 <= page_size <= 100):
            return _error_response("VALIDATION_ERROR", "page_size must be between 1 and 100.", 422)

        user_id = request.args.get("user_id")
        event_id = request.args.get("event_id")
        status = request.args.get("status")

        if status is not None and status not in VALID_STATUSES:
            return _error_response(
                "VALIDATION_ERROR",
                f"status must be one of {sorted(VALID_STATUSES)}.",
                422,
            )

        items, total = service.list_registrations(user_id, event_id, status, page, page_size)
        return jsonify(_paginate(items, page, page_size, total)), 200

    # ------------------------------------------------------------------
    # GET /api/v1/registrations/stats — Statistiche evento  (REQ-REG-B08)
    #
    # Registrata PRIMA della route con <registration_id>: altrimenti 'stats'
    # verrebbe interpretato come l'id di una registrazione (REQ-REG-B08
    # criterio 8).
    # ------------------------------------------------------------------

    @app.route("/api/v1/registrations/stats", methods=["GET"])
    def registration_stats():
        event_id = request.args.get("event_id")
        if not event_id:
            return _error_response("VALIDATION_ERROR", "event_id query parameter is required.", 422)

        try:
            stats = service.get_stats(event_id)
        except EventNotFoundForStatsError:
            return _error_response("NOT_FOUND", f"Event '{event_id}' not found.", 404)
        except _DOMAIN_ERRORS as exc:
            return _map_domain_error(exc)

        return jsonify(stats), 200

    # ------------------------------------------------------------------
    # GET /api/v1/registrations/<id> — Lettura singola  (REQ-REG-E03)
    # ------------------------------------------------------------------

    @app.route("/api/v1/registrations/<registration_id>", methods=["GET"])
    def get_registration(registration_id):
        try:
            registration = service.get_registration(registration_id)
        except RegistrationNotFoundError:
            return _error_response("NOT_FOUND", f"Registration '{registration_id}' not found.", 404)
        return jsonify(_serialize_registration(registration)), 200

    # ------------------------------------------------------------------
    # PATCH /api/v1/registrations/<id> — Transizione di stato  (REQ-REG-E04)
    # ------------------------------------------------------------------

    @app.route("/api/v1/registrations/<registration_id>", methods=["PATCH"])
    def update_registration(registration_id):
        data = request.get_json(force=True, silent=False)
        if data is None:
            return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

        errors = _validate_patch_input(data)
        if errors:
            return _error_response("VALIDATION_ERROR", "; ".join(errors), 422)

        try:
            registration = service.update_status(registration_id, data["status"])
        except RegistrationNotFoundError:
            return _error_response("NOT_FOUND", f"Registration '{registration_id}' not found.", 404)
        except _DOMAIN_ERRORS as exc:
            return _map_domain_error(exc)

        return jsonify(_serialize_registration(registration)), 200

    # ------------------------------------------------------------------
    # DELETE /api/v1/registrations/<id> — Cancellazione  (REQ-REG-E05)
    # ------------------------------------------------------------------

    @app.route("/api/v1/registrations/<registration_id>", methods=["DELETE"])
    def delete_registration(registration_id):
        try:
            service.delete_registration(registration_id)
        except RegistrationNotFoundError:
            return _error_response("NOT_FOUND", f"Registration '{registration_id}' not found.", 404)
        return "", 204
