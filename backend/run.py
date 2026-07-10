import os

from app import create_app
from app.extensions import socketio


app = create_app()


if __name__ == "__main__":
    from waitress import serve
    host = os.getenv("API_HOST", "127.0.0.1")
    port = int(os.getenv("API_PORT", "5000"))
    print(f"Starting production server on http://{host}:{port} with 100 threads...")
    serve(app, host=host, port=port, threads=100)
