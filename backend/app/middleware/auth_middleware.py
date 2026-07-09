from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from ..api import error
from ..extensions import db
from ..models import User


def create_token(user, expires_minutes=None, token_type="access"):
    config_key = "JWT_REFRESH_EXPIRES_MINUTES" if token_type == "refresh" else "JWT_EXPIRES_MINUTES"
    expires_minutes = expires_minutes or current_app.config[config_key]
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "token_type": token_type,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def decode_token(token, expected_type=None):
    payload = jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
    if expected_type and payload.get("token_type", "access") != expected_type:
        raise jwt.InvalidTokenError("invalid token type")
    return payload


def auth_required(fn=None, *, token_type="access"):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return error("missing Authorization Bearer token", 401)

            token = header.split(" ", 1)[1].strip()
            try:
                payload = decode_token(token, expected_type=token_type)
            except jwt.ExpiredSignatureError:
                return error("token expired", 401)
            except jwt.PyJWTError:
                return error("invalid token", 401)

            user_id = payload.get("sub") or payload.get("user_id")
            user = db.session.get(User, int(user_id))
            if not user or not user.is_active:
                return error("user disabled or not found", 401)

            g.current_user = user
            g.jwt_payload = payload
            return view_func(*args, **kwargs)

        return wrapper

    if fn is None:
        return decorator
    return decorator(fn)


def refresh_required(fn):
    return auth_required(fn, token_type="refresh")


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        @auth_required
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                return error("permission denied", 403)
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
