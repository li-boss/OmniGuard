from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS

from .api import register_api
from .extensions import db, socketio
from .services.ws_handler import init_socket_events


def create_app(config_override=None):
    root_dir = Path(__file__).resolve().parents[2]
    load_dotenv(root_dir / ".env", override=False)

    from config import Config

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)
    if config_override:
        app.config.update(config_override)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    CORS(app, resources={r"/api/*": {"origins": app.config["FRONTEND_ORIGIN"]}})
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins=app.config["FRONTEND_ORIGIN"])

    register_api(app)
    init_socket_events(socketio)

    @app.get("/api/system/health")
    def health():
        return jsonify({
            "code": 0,
            "message": "ok",
            "data": {
                "service": "smart-campus-security",
                "status": "UP",
                "time": datetime.now(timezone.utc).isoformat(),
                "database": "UP",
            },
        })

    with app.app_context():
        from .models import User  # noqa: F401

        db.create_all()
        _seed_admin(app)

    return app


def _seed_admin(app):
    from .models import User

    username = app.config["DEFAULT_ADMIN_USER"]
    if User.query.filter_by(username=username).first():
        return

    admin = User(username=username, role="admin")
    admin.set_password(app.config["DEFAULT_ADMIN_PASSWORD"])
    db.session.add(admin)
    db.session.commit()
