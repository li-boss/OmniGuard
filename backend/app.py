from pathlib import Path
from flask import Flask
from flask_cors import CORS

BASE_DIR = Path(__file__).resolve().parent
from flask_jwt_extended import JWTManager
from services.ws_handler import socketio
jwt = JWTManager()

from api.dashboard_api import dashboard_bp
from api.event_api import event_bp
from api.rule_api import rule_bp, camera_bp
from api.user_api import auth_bp, user_bp
from config import Config
from models import db


def create_app(config_class=Config):
    app = Flask(__name__)
    if isinstance(config_class, dict):
        app.config.from_object(Config)
        app.config.update(config_class)
    else:
        app.config.from_object(config_class)

    if app.testing:
        app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'instance' / 'test_temp.db'}"

    if app.config.get("SQLALCHEMY_DATABASE_URI") == "sqlite:///:memory:":
        from sqlalchemy.pool import StaticPool
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "poolclass": StaticPool,
            "connect_args": {"check_same_thread": False}
        }

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)
    from services.ws_handler import init_socket_events
    init_socket_events(socketio)

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(user_bp, url_prefix="/api/users")
    app.register_blueprint(rule_bp, url_prefix="/api/zones")
    app.register_blueprint(camera_bp, url_prefix="/api/cameras")
    app.register_blueprint(event_bp, url_prefix="/api/alarms")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")

    from api.face_api import face_bp
    from api.log_api import log_bp
    from api.stream_api import stream_bp
    app.register_blueprint(face_bp)
    app.register_blueprint(log_bp)
    app.register_blueprint(stream_bp, url_prefix="/api/streams")

    # Ensure directories exist
    (BASE_DIR / 'data' / 'faces').mkdir(parents=True, exist_ok=True)

    @app.get("/api/system/health")
    def health():
        from datetime import datetime, timezone
        from flask import jsonify
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
        db.create_all()
        _seed_admin(app)

    # Warmup models on cold startup
    import os
    import atexit
    from core_cv.model_loader import ModelLoader
    from core_cv.pipeline import CameraPipelineManager
    
    ModelLoader.warmup()
    
    # Initialize and start the CameraPipelineManager
    manager = CameraPipelineManager(app)
    if not app.testing:
        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            manager.start()
            atexit.register(manager.stop)
            
            from services.scheduler import scheduler_svc
            scheduler_svc.start()
            atexit.register(scheduler_svc.stop)

    return app


def _seed_admin(app):
    from models import User
    username = app.config.get("DEFAULT_ADMIN_USER", "admin")
    if User.query.filter_by(username=username).first():
        return
    admin = User(username=username, role="admin")
    admin.set_password(app.config.get("DEFAULT_ADMIN_PASSWORD", "admin123"))
    db.session.add(admin)
    db.session.commit()


if __name__ == "__main__":
    socketio.run(create_app(), host="0.0.0.0", port=5000, debug=True)
