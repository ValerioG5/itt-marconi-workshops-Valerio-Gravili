from flask import jsonify, request


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


def register_routes(app, service):
    """Registra tutte le route dell'app Flask."""

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "event-service"}), 200

    @app.errorhandler(400)
    def handle_bad_request(e):
        return _error_response("MALFORMED_JSON", "Request body is not valid JSON.", 400)
