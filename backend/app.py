from pathlib import Path
import logging
from flask import Flask
from flask_cors import CORS
from flasgger import Swagger

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

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
from swagger_docs import SWAGGER_CONFIG, SWAGGER_TEMPLATE


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
    Swagger(app, config=SWAGGER_CONFIG, template=SWAGGER_TEMPLATE)
    
    from flask import jsonify
    from flask_jwt_extended.exceptions import JWTExtendedException
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error_string):
        logging.error(f"JWT invalid token: {error_string}")
        return jsonify({'code': 422, 'message': f'Invalid token: {error_string}'}), 422
    
    @jwt.unauthorized_loader
    def missing_token_callback(error_string):
        logging.error(f"JWT missing token: {error_string}")
        return jsonify({'code': 401, 'message': f'Missing Authorization Header: {error_string}'}), 401
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        logging.error(f"JWT expired token")
        return jsonify({'code': 401, 'message': 'Token has expired'}), 401
    
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
    from api.stream_api import stream_bp
    from api.alert_api import alert_bp
    from api.report_api import report_bp
    from api.access_log_api import access_log_bp
    app.register_blueprint(face_bp)
    app.register_blueprint(stream_bp, url_prefix="/api/streams")
    app.register_blueprint(alert_bp)
    app.register_blueprint(report_bp, url_prefix="/api/reports")
    app.register_blueprint(access_log_bp)

    (BASE_DIR / 'data' / 'faces').mkdir(parents=True, exist_ok=True)

    @app.get("/api/system/health")
    def health():
        from datetime import datetime, timezone
        from flask import jsonify
        import threading
        from api.stream_api import get_active_streams
        return jsonify({
            "code": 0,
            "message": "ok",
            "data": {
                "service": "smart-campus-security",
                "status": "UP",
                "time": datetime.now(timezone.utc).isoformat(),
                "database": "UP",
                "threads": threading.active_count(),
                "active_streams": get_active_streams()
            },
        })

    with app.app_context():
        db.create_all()
        from services.schema_migrations import ensure_alarm_video_path_column
        ensure_alarm_video_path_column()
        _seed_admin(app)

    import os
    import atexit
    from core_cv.model_loader import ModelLoader
    from core_cv.pipeline import CameraPipelineManager
    
    ModelLoader.warmup()
    
    try:
        from services.model_downloader import preload_models
        preload_models()
    except Exception as e:
        logging.warning(f"AI model preload skipped: {e}")
    
    app.pipeline_manager = CameraPipelineManager(app)
    manager = app.pipeline_manager
    app.config['pipeline_manager'] = manager
    if not app.testing:
        if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
            from services.rtmp_pusher import rtmp_pusher_svc
            rtmp_pusher_svc.start()
            atexit.register(rtmp_pusher_svc.stop)

            manager.start()
            from services.alarm_video_recorder import get_alarm_video_recorder
            alarm_video_recorder = get_alarm_video_recorder(app)
            atexit.register(alarm_video_recorder.stop)
            atexit.register(manager.stop)
            
            from services.scheduler import scheduler_svc
            scheduler_svc.start(app)
            atexit.register(scheduler_svc.stop)
            
            from api.face_api import init_auto_recalculate
            init_auto_recalculate(app)

            from services.alert_handler import get_alert_handler
            alert_handler = get_alert_handler()
            alert_handler.start()
            atexit.register(alert_handler.stop)

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
    from waitress import serve
    app_instance = create_app()
    print("Starting production server on http://0.0.0.0:5000 with 100 threads...")
    serve(app_instance, host="0.0.0.0", port=5000, threads=100)
