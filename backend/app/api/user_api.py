from flask import Blueprint, g, request

from ..extensions import db
from ..middleware.auth_middleware import auth_required, create_token, refresh_required, role_required
from ..models import AccessLog, User
from . import error, success


auth_bp = Blueprint("auth", __name__)
user_bp = Blueprint("users", __name__)


def _parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _user_payload(user):
    access_token = create_token(user)
    refresh_token = create_token(user, token_type="refresh")
    return {
        "user": user.to_dict(),
        "token": access_token,
        "tokenType": "Bearer",
        "token_type": "Bearer",
        "accessToken": access_token,
        "access_token": access_token,
        "refreshToken": refresh_token,
        "refresh_token": refresh_token,
    }


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

    user = User(
        username=username,
        real_name=payload.get("realName") or payload.get("real_name") or payload.get("name"),
        role=role,
        phone=payload.get("phone"),
        department=payload.get("department"),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.flush()
    _write_log(user, "auth.register")
    db.session.commit()
    return success(_user_payload(user), "registered", 201)


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
    return success(_user_payload(user))


@auth_bp.post("/refresh")
@refresh_required
def refresh():
    return success(_user_payload(g.current_user))


@user_bp.get("/me")
@auth_required
def me():
    return success(g.current_user.to_dict())


@user_bp.put("/me/password")
@auth_required
def change_password():
    payload = request.get_json(silent=True) or {}
    old_password = str(payload.get("oldPassword") or payload.get("old_password") or "")
    new_password = str(payload.get("newPassword") or payload.get("new_password") or "")
    if not g.current_user.check_password(old_password):
        return error("old password is incorrect", 400)
    if len(new_password) < 6:
        return error("new password must be at least 6 chars", 400)

    g.current_user.set_password(new_password)
    _write_log(g.current_user, "user.change_password")
    db.session.commit()
    return success(message="password updated")


@user_bp.get("")
@role_required("admin")
def list_users():
    page = max(int(request.args.get("page", "1")), 1)
    page_size = min(max(int(request.args.get("pageSize") or request.args.get("page_size") or "20"), 1), 100)
    keyword = str(request.args.get("keyword") or "").strip()

    query = User.query
    if keyword:
        query = query.filter(User.username.contains(keyword))

    pagination = query.order_by(User.id.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    return success({
        "items": [user.to_dict() for user in pagination.items],
        "page": page,
        "pageSize": page_size,
        "page_size": page_size,
        "total": pagination.total,
    })


@user_bp.post("")
@role_required("admin")
def create_user():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if len(username) < 3 or len(password) < 6:
        return error("username must be at least 3 chars and password at least 6 chars", 400)
    if User.query.filter_by(username=username).first():
        return error("username already exists", 409)

    user = User(
        username=username,
        real_name=payload.get("realName") or payload.get("real_name") or payload.get("name"),
        role=str(payload.get("role") or "operator"),
        phone=payload.get("phone"),
        department=payload.get("department"),
        is_active=_parse_bool(payload.get("isActive", payload.get("is_active", True))),
    )
    user.set_password(password)
    db.session.add(user)
    _write_log(g.current_user, f"user.create:{username}")
    db.session.commit()
    return success(user.to_dict(), "user created", 201)


@user_bp.put("/<int:user_id>")
@role_required("admin")
def update_user(user_id):
    user = db.get_or_404(User, user_id)
    payload = request.get_json(silent=True) or {}
    if "realName" in payload or "real_name" in payload or "name" in payload:
        user.real_name = payload.get("realName") or payload.get("real_name") or payload.get("name")
    if "role" in payload:
        user.role = str(payload["role"])
    if "phone" in payload:
        user.phone = payload.get("phone")
    if "department" in payload:
        user.department = payload.get("department")
    if "isActive" in payload or "is_active" in payload:
        user.is_active = _parse_bool(payload.get("isActive", payload.get("is_active")))
    if payload.get("password"):
        if len(payload["password"]) < 6:
            return error("password must be at least 6 chars", 400)
        user.set_password(payload["password"])

    _write_log(g.current_user, f"user.update:{user.username}")
    db.session.commit()
    return success(user.to_dict(), "user updated")


@user_bp.delete("/<int:user_id>")
@role_required("admin")
def delete_user(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == g.current_user.id:
        return error("cannot delete current user", 400)

    db.session.delete(user)
    _write_log(g.current_user, f"user.delete:{user.username}")
    db.session.commit()
    return success(message="user deleted")
