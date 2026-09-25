from flask import Flask

from app import config
from app.clients.event_client import EventClient
from app.clients.user_client import UserClient
from app.routes import register_routes
from app.service import RegistrationService


def _make_repository():
    backend = config.STORAGE_BACKEND
    if backend == "json":
        from app.repository.json_repo import JsonRegistrationRepository
        return JsonRegistrationRepository(config.DATA_DIR)
    if backend == "sqlite":
        from app.repository.sqlite_repo import SqliteRegistrationRepository
        return SqliteRegistrationRepository(config.DATA_DIR)
    # default: memory
    from app.repository.memory import MemoryRegistrationRepository
    return MemoryRegistrationRepository()


def create_app(repository=None, user_client=None, event_client=None):
    app = Flask(__name__)
    if repository is None:
        repository = _make_repository()
    if user_client is None:
        user_client = UserClient(config.USER_SERVICE_URL, config.DEPENDENCY_TIMEOUT)
    if event_client is None:
        event_client = EventClient(config.EVENT_SERVICE_URL, config.DEPENDENCY_TIMEOUT)
    service = RegistrationService(repository, user_client, event_client)
    register_routes(app, service)
    return app
