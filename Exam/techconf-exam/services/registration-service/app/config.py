import os

PORT               = int(os.environ.get("PORT", 5003))
USER_SERVICE_URL   = os.environ.get("USER_SERVICE_URL",  "http://localhost:5001")
EVENT_SERVICE_URL  = os.environ.get("EVENT_SERVICE_URL", "http://localhost:5002")
STORAGE_BACKEND    = os.environ.get("STORAGE_BACKEND", "memory")
DATA_DIR           = os.environ.get("DATA_DIR", "./data")
DEPENDENCY_TIMEOUT = 2
