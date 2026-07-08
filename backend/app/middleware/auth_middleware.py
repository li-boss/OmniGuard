from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
from flask import current_app, g, request

from ..api import error
from ..extensions import db
from ..models import User


def create_token(user, expires_minutes=None):
    expires_minutes = expires_minutes or current_app.config["JWT_EXPIRES_MINUTES"]
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return error("missing Authorization Bearer token", 401)

        token = header.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
        except jwt.ExpiredSignatureError:
            return error("token expired", 401)
        except jwt.PyJWTError:
            return error("invalid token", 401)

        user = db.session.get(User, int(payload["sub"]))
        if not user or not user.is_active:
            return error("user disabled or not found", 401)

        g.current_user = user
        return fn(*args, **kwargs)

    return wrapper
