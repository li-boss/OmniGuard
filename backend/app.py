from flask import Flask
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO

from api.dashboard_api import dashboard_bp
from api.event_api import event_bp
from api.rule_api import rule_bp, camera_bp
from api.user_api import user_bp
from config import Config
from models import db

socketio = SocketIO(cors_allowed_origins="*")
jwt = JWTManager()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)
    jwt.init_app(app)
    socketio.init_app(app)

    app.register_blueprint(user_bp, url_prefix="/api/auth")
    app.register_blueprint(rule_bp, url_prefix="/api/zones")
    app.register_blueprint(camera_bp, url_prefix="/api/cameras")
    app.register_blueprint(event_bp, url_prefix="/api/alarms")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")

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

    return app


if __name__ == "__main__":
    socketio.run(create_app(), host="0.0.0.0", port=5000, debug=True)
