import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_cors import CORS

db = SQLAlchemy()
jwt = JWTManager()


def create_app(config_name=None):
    app = Flask(__name__)

    config_name = config_name or os.getenv('FLASK_ENV', 'development')
    app.config.from_object(f'backend.config.{config_name.capitalize()}Config')

    if os.path.exists(os.path.join(os.path.dirname(__file__), '..', '.env')):
        from dotenv import load_dotenv
        load_dotenv()

    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
        'DATABASE_URI',
        'sqlite:///campus_security.db',
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-secret-change-in-production')
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

    CORS(app, resources={r"/api/*": {"origins": "*"}})

    db.init_app(app)
    jwt.init_app(app)

    from backend.api.event_api import event_bp
    from backend.api.dashboard_api import dashboard_bp
    app.register_blueprint(event_bp)
    app.register_blueprint(dashboard_bp)

    from backend.services.ws_handler import socketio
    socketio.init_app(app)

    from backend.services.scheduler import scheduler_svc

    @app.before_request
    def start_scheduler():
        if not scheduler_svc.scheduler.running:
            scheduler_svc.start()

    with app.app_context():
        db.create_all()

    return app


if __name__ == '__main__':
    import argparse
    from backend.services.ws_handler import socketio
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=int(os.getenv('PORT', 5000)))
    parser.add_argument('--host', type=str, default='0.0.0.0')
    args = parser.parse_args()
    app = create_app()
    socketio.run(app, host=args.host, port=args.port, debug=True, allow_unsafe_werkzeug=True)
