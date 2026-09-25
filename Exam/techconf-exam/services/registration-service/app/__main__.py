from app import create_app
from app.config import PORT

if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=PORT)
