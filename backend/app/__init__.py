import atexit
from datetime import datetime, timezone
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from sqlalchemy import text

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
        _ensure_sqlite_schema()
        _seed_admin(app)

    if not app.testing and (not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true"):
        from .services.scheduler import scheduler_svc

        scheduler_svc.start()
        atexit.register(scheduler_svc.stop)

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


def _ensure_sqlite_schema():
    if db.engine.dialect.name != "sqlite":
        return

    migrations = {
        "user": [
            ("real_name", "VARCHAR(64)"),
            ("phone", "VARCHAR(32)"),
            ("department", "VARCHAR(128)"),
            ("updated_at", "DATETIME"),
        ],
        "zone": [
            ("stay_seconds", "INTEGER DEFAULT 5 NOT NULL"),
        ],
        "alarm_event": [
            ("detection_data", "JSON"),
            ("handler_id", "INTEGER"),
            ("escalation_level", "INTEGER DEFAULT 0 NOT NULL"),
            ("escalation_deadline", "DATETIME"),
            ("dingtalk_notified", "BOOLEAN DEFAULT 0 NOT NULL"),
            ("updated_at", "DATETIME"),
        ],
    }

    with db.engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        }
        for table_name, columns in migrations.items():
            if table_name not in tables:
                continue
            existing_columns = {
                row[1]
                for row in connection.execute(text(f'PRAGMA table_info("{table_name}")'))
            }
            for column_name, column_sql in columns:
                if column_name not in existing_columns:
                    connection.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN {column_name} {column_sql}'))

        if "user" in tables:
            connection.execute(text(
                'UPDATE "user" SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)'
            ))
        if "alarm_event" in tables:
            connection.execute(text(
                'UPDATE alarm_event SET updated_at = COALESCE(updated_at, occurred_at, CURRENT_TIMESTAMP)'
            ))
