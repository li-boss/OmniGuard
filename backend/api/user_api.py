"""
用户与鉴权 API。

对应联调协议：
- IAuth: 注册、登录、刷新 token。
- IUser: 当前用户信息、修改密码。
"""

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from backend.middleware.auth_middleware import (
    generate_token,
    login_required,
    refresh_token_required,
    role_required,
)
from backend.models import User, db


user_bp = Blueprint("user_api", __name__)


def _json():
    """安全读取 JSON 请求体。"""

    return request.get_json(silent=True) or {}


def _success(data=None, message="ok", status=200):
    """统一成功响应格式。"""

    return jsonify({"code": status, "message": message, "data": data or {}}), status


def _error(message, status):
    """统一错误响应格式。"""

    return jsonify({"code": status, "message": message, "data": {}}), status


@user_bp.post("/api/auth/register")
def register():
    """用户注册。"""

    data = _json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return _error("username 和 password 不能为空", 400)
    if len(password) < 6:
        return _error("密码长度不能少于 6 位", 400)

    user = User(
        username=username,
        real_name=data.get("real_name") or data.get("name"),
        role=data.get("role", "security"),
        phone=data.get("phone"),
        department=data.get("department"),
    )
    user.set_password(password)

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("用户名已存在", 409)
    except SQLAlchemyError:
        db.session.rollback()
        return _error("注册失败", 500)

    return _success({"user": user.to_dict()}, "注册成功", 201)


@user_bp.post("/api/auth/login")
def login():
    """用户登录，返回 access token 和 refresh token。"""

    data = _json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return _error("username 和 password 不能为空", 400)

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return _error("用户名或密码错误", 401)
    if not user.is_active:
        return _error("账号已禁用", 403)

    return _success(
        {
            "token_type": "Bearer",
            "access_token": generate_token(user, token_type="access"),
            "refresh_token": generate_token(user, token_type="refresh"),
            "user": user.to_dict(),
        },
        "登录成功",
    )


@user_bp.post("/api/auth/refresh")
@refresh_token_required
def refresh_token():
    """使用 refresh token 换取新的 token。"""

    return _success(
        {
            "token_type": "Bearer",
            "access_token": generate_token(g.current_user, token_type="access"),
            "refresh_token": generate_token(g.current_user, token_type="refresh"),
        },
        "刷新成功",
    )


@user_bp.get("/api/users/me")
@login_required
def get_current_user():
    """获取当前登录用户信息。"""

    return _success({"user": g.current_user.to_dict()})


@user_bp.put("/api/users/me/password")
@login_required
def change_password():
    """当前用户修改自己的密码。"""

    data = _json()
    old_password = data.get("old_password") or ""
    new_password = data.get("new_password") or ""

    if not old_password or not new_password:
        return _error("旧密码和新密码不能为空", 400)
    if len(new_password) < 6:
        return _error("新密码长度不能少于 6 位", 400)
    if not g.current_user.check_password(old_password):
        return _error("旧密码错误", 400)

    g.current_user.set_password(new_password)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("密码修改失败", 500)

    return _success(message="密码修改成功")


@user_bp.get("/api/users")
@role_required("admin")
def list_users():
    """管理员分页查询用户列表。"""

    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    keyword = (request.args.get("keyword") or "").strip()

    query = User.query
    if keyword:
        query = query.filter(User.username.contains(keyword))

    pagination = query.order_by(User.id.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    return _success(
        {
            "items": [item.to_dict() for item in pagination.items],
            "total": pagination.total,
            "page": page,
            "page_size": page_size,
        }
    )


@user_bp.post("/api/users")
@role_required("admin")
def create_user():
    """管理员创建用户。"""

    data = _json()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return _error("username 和 password 不能为空", 400)
    if len(password) < 6:
        return _error("密码长度不能少于 6 位", 400)

    user = User(
        username=username,
        real_name=data.get("real_name") or data.get("name"),
        role=data.get("role", "security"),
        phone=data.get("phone"),
        department=data.get("department"),
        is_active=data.get("is_active", True),
    )
    user.set_password(password)

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _error("用户名已存在", 409)
    except SQLAlchemyError:
        db.session.rollback()
        return _error("创建用户失败", 500)

    return _success({"user": user.to_dict()}, "创建成功", 201)


@user_bp.put("/api/users/<int:user_id>")
@role_required("admin")
def update_user(user_id):
    """管理员更新用户资料。"""

    user = db.session.get(User, user_id)
    if not user:
        return _error("用户不存在", 404)

    data = _json()
    if "real_name" in data:
        user.real_name = data.get("real_name")
    if "name" in data:
        user.real_name = data.get("name")
    if "role" in data:
        user.role = data.get("role")
    if "phone" in data:
        user.phone = data.get("phone")
    if "department" in data:
        user.department = data.get("department")
    if "is_active" in data:
        user.is_active = bool(data.get("is_active"))
    if data.get("password"):
        if len(data["password"]) < 6:
            return _error("密码长度不能少于 6 位", 400)
        user.set_password(data["password"])

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("更新用户失败", 500)

    return _success({"user": user.to_dict()}, "更新成功")


@user_bp.delete("/api/users/<int:user_id>")
@role_required("admin")
def delete_user(user_id):
    """管理员删除用户。"""

    user = db.session.get(User, user_id)
    if not user:
        return _error("用户不存在", 404)
    if user.id == g.current_user.id:
        return _error("不能删除当前登录账号", 400)

    db.session.delete(user)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("删除用户失败", 500)

    return _success(message="删除成功")
