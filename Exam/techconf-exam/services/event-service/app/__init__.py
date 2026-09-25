from flask import Flask

from app import config
from app.clients.user_client import UserClient
from app.routes import register_routes
from app.service import EventService


def _make_repository():
    backend = config.STORAGE_BACKEND
    if backend == "json":
        from app.repository.json_repo import JsonEventRepository
        return JsonEventRepository(config.DATA_DIR)
    if backend == "sqlite":
        from app.repository.sqlite_repo import SqliteEventRepository
        return SqliteEventRepository(config.DATA_DIR)
    # default: memory
    from app.repository.memory import MemoryEventRepository
    return MemoryEventRepository()


def create_app(repository=None, user_client=None):
    app = Flask(__name__)
    if repository is None:
        repository = _make_repository()
    if user_client is None:
        user_client = UserClient(config.USER_SERVICE_URL, config.DEPENDENCY_TIMEOUT)
    service = EventService(repository, user_client)
    register_routes(app, service)
    return app
