from flask import Flask

from app import config
from app.routes import register_routes
from app.service import UserService


def _make_repository():
    backend = config.STORAGE_BACKEND
    if backend == "json":
        from app.repository.json_repo import JsonUserRepository
        return JsonUserRepository(config.DATA_DIR)
    if backend == "sqlite":
        from app.repository.sqlite_repo import SqliteUserRepository
        return SqliteUserRepository(config.DATA_DIR)
    # default: memory
    from app.repository.memory import MemoryUserRepository
    return MemoryUserRepository()


def create_app(repository=None):
    app = Flask(__name__)
    if repository is None:
        repository = _make_repository()
    service = UserService(repository)
    register_routes(app, service)
    return app
