import re

from flask import jsonify, request

from app.repository.base import EmailAlreadyExistsError, UserNotFoundError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_ROLES = {"attendee", "speaker", "organizer"}
_EMAIL_RE = re.compile(r'^[^@]+@[^@]+\.[^@]+')


# ---------------------------------------------------------------------------
# Helpers (module-level, reusable by route handlers)
# ---------------------------------------------------------------------------

def _error_response(code, message, status, details=None):
    """Costruisce una risposta di errore standard."""
    body = {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }
    return jsonify(body), status


def _validate_user_input(data: dict, partial: bool = False) -> list:
    """Valida i campi in input; restituisce lista di messaggi di errore."""
    errors = []

    # first_name
    if "first_name" in data:
        fn = data["first_name"]
        if not isinstance(fn, str) or not (1 <= len(fn) <= 50):
            errors.append("first_name must be a string of 1–50 characters.")
    elif not partial:
        errors.append("first_name is required.")

    # last_name
    if "last_name" in data:
        ln = data["last_name"]
        if not isinstance(ln, str) or not (1 <= len(ln) <= 50):
            errors.append("last_name must be a string of 1–50 characters.")
    elif not partial:
        errors.append("last_name is required.")

    # email
    if "email" in data:
        em = data["email"]
        if not isinstance(em, str) or not _EMAIL_RE.match(em):
            errors.append("email must be a valid email address (must contain @ and a domain).")
    elif not partial:
        errors.append("email is required.")

    # company (optional, nullable)
    if "company" in data and data["company"] is not None:
        co = data["company"]
        if not isinstance(co, str) or len(co) > 100:
            errors.append("company must be a string of at most 100 characters.")

    # role (optional)
    if "role" in data and data["role"] not in VALID_ROLES:
        errors.append(f"role must be one of {sorted(VALID_ROLES)}.")

    return errors


def _serialize_user(user: dict) -> dict:
    """Estrae solo i campi definiti nel contratto OpenAPI (additionalProperties: false)."""
    return {
        "id": user["id"],
        "first_name": user["first_name"],
        "last_name": user["last_name"],
        "email": user["email"],
        "company": user.get("company"),
        "role": user["role"],
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
    }


def _paginate(page_items: list, page: int, page_size: int, total: int) -> dict:
    """Costruisce il body paginato serializzando ogni utente."""
    return {
        "items": [_serialize_user(u) for u in page_items],
        "page": page,
        "page_size": page_size,
        "total": total,
    }


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
        return jsonify({"status": "ok", "service": "user-service"}), 200

    # ------------------------------------------------------------------
    # Error handlers
    # ------------------------------------------------------------------

    @app.errorhandler(400)
    def handle_bad_request(e):
        return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

    # ------------------------------------------------------------------
    # POST /api/v1/users — Creazione utente  (REQ-USR-E01)
    # ------------------------------------------------------------------

    @app.route("/api/v1/users", methods=["POST"])
    def create_user():
        # silent=False fa sì che Flask lanci un 400 se il JSON è malformato
        data = request.get_json(force=True, silent=False)
        if data is None:
            return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)

        errors = _validate_user_input(data, partial=False)
        if errors:
            return _error_response("VALIDATION_ERROR", "; ".join(errors), 422)

        try:
            user = service.create_user(data)
        except EmailAlreadyExistsError:
            return _error_response("EMAIL_ALREADY_EXISTS", "Email already registered.", 409)

        resp = jsonify(_serialize_user(user))
        resp.status_code = 201
        resp.headers["Location"] = f"/api/v1/users/{user['id']}"
        return resp

    # ------------------------------------------------------------------
    # GET /api/v1/users — Lista paginata  (REQ-USR-E02, REQ-USR-B03)
    # ------------------------------------------------------------------

    @app.route("/api/v1/users", methods=["GET"])
    def list_users():
        # Validazione parametri di paginazione
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 20))
        except ValueError:
            return _error_response("VALIDATION_ERROR", "page and page_size must be integers.", 422)

        if page < 1:
            return _error_response("VALIDATION_ERROR", "page must be >= 1.", 422)
        if not (1 <= page_size <= 100):
            return _error_response("VALIDATION_ERROR", "page_size must be between 1 and 100.", 422)

        role = request.args.get("role")
        email = request.args.get("email")

        # Validazione role filter  (REQ-USR-B03 criterio 5)
        if role is not None and role not in VALID_ROLES:
            return _error_response(
                "VALIDATION_ERROR",
                f"role must be one of {sorted(VALID_ROLES)}.",
                422,
            )

        items, total = service.list_users(role, email, page, page_size)
        return jsonify(_paginate(items, page, page_size, total)), 200
