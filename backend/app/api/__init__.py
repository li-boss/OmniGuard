from flask import jsonify


def success(data=None, message="ok", status=200):
    return jsonify({
        "code": 0,
        "message": message,
        "data": data,
    }), status


def error(message, status=400, data=None):
    return jsonify({
        "code": status,
        "message": message,
        "data": data,
    }), status


def register_api(app):
    from .dashboard_api import dashboard_bp
    from .event_api import alarm_bp
    from .face_api import face_bp
    from .log_api import log_bp
    from .rule_api import zone_bp
    from .stream_api import stream_bp
    from .user_api import auth_bp, user_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(user_bp, url_prefix="/api/users")
    app.register_blueprint(face_bp, url_prefix="/api/faces")
    app.register_blueprint(zone_bp, url_prefix="/api/zones")
    app.register_blueprint(alarm_bp, url_prefix="/api/alarms")
    app.register_blueprint(dashboard_bp, url_prefix="/api/dashboard")
    app.register_blueprint(log_bp, url_prefix="/api/access-logs")
    app.register_blueprint(stream_bp, url_prefix="/api/streams")
