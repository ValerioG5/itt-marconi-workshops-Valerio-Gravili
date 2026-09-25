import os

PORT             = int(os.environ.get("PORT", 5001))
STORAGE_BACKEND  = os.environ.get("STORAGE_BACKEND", "memory")
DATA_DIR         = os.environ.get("DATA_DIR", "./data")
