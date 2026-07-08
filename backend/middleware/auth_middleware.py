from functools import wraps
from flask import g, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import User, db

def _error(message, status):
    return jsonify({"code": status, "message": message, "data": {}}), status

def login_required(view_func):
    """Requires access token and loads g.current_user."""
    @wraps(view_func)
    @jwt_required()
    def wrapper(*args, **kwargs):
        try:
            identity = get_jwt_identity()
            if not identity:
                return _error("缺少 Bearer Token", 401)
            user_id = int(identity)
            user = db.session.get(User, user_id)
        except (ValueError, TypeError):
            return _error("无效 Token", 401)
            
        if not user:
            return _error("用户不存在", 401)
        if hasattr(user, "is_active") and not user.is_active:
            return _error("账号已禁用", 403)
            
        g.current_user = user
        return view_func(*args, **kwargs)
    return wrapper

def role_required(*roles):
    """Requires login and verifies user role."""
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                return _error("权限不足", 403)
            return view_func(*args, **kwargs)
        return wrapper
    return decorator
