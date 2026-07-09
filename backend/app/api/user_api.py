from flask import Blueprint, g, request

from ..extensions import db
from ..middleware.auth_middleware import auth_required, create_token
from ..models import AccessLog, User
from . import error, success


auth_bp = Blueprint("auth", __name__)
user_bp = Blueprint("users", __name__)


def _write_log(user, action):
    db.session.add(AccessLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        ip=request.remote_addr,
        user_agent=request.headers.get("User-Agent", "")[:255],
    ))


@auth_bp.post("/register")
def register():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    role = str(payload.get("role", "operator")).strip() or "operator"

    if len(username) < 3 or len(password) < 6:
        return error("username must be at least 3 chars and password at least 6 chars", 400)
    if User.query.filter_by(username=username).first():
        return error("username already exists", 409)

    user = User(username=username, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    _write_log(user, "auth.register")
    db.session.commit()
    return success({"user": user.to_dict(), "token": create_token(user)}, "registered", 201)


@auth_bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return error("invalid username or password", 401)
    if not user.is_active:
        return error("user is disabled", 403)

    _write_log(user, "auth.login")
    db.session.commit()
    return success({"user": user.to_dict(), "token": create_token(user)})


@auth_bp.post("/refresh")
@auth_required
def refresh():
    return success({"token": create_token(g.current_user)})


@user_bp.get("/me")
@auth_required
def me():
    return success(g.current_user.to_dict())


@user_bp.put("/me/password")
@auth_required
def change_password():
    payload = request.get_json(silent=True) or {}
    old_password = str(payload.get("oldPassword", ""))
    new_password = str(payload.get("newPassword", ""))
    if not g.current_user.check_password(old_password):
        return error("old password is incorrect", 400)
    if len(new_password) < 6:
        return error("new password must be at least 6 chars", 400)

    g.current_user.set_password(new_password)
    _write_log(g.current_user, "user.change_password")
    db.session.commit()
    return success(message="password updated")
