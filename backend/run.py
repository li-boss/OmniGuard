import os

from app import create_app
from app.extensions import socketio


app = create_app()


if __name__ == "__main__":
    socketio.run(
        app,
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "5000")),
        debug=os.getenv("APP_ENV", "development") == "development",
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
