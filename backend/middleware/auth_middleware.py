"""
JWT 鉴权中间件。

提供 access token 鉴权、refresh token 鉴权和角色鉴权。
"""

from datetime import datetime, timezone
from functools import wraps

import jwt
from flask import current_app, g, jsonify, request

from backend.models import User, db


def generate_token(user, token_type="access"):
    """
    生成 JWT。

    token_type:
    - access: 普通接口访问令牌。
    - refresh: 刷新令牌，用于换取新的 access token。
    """

    now = datetime.now(timezone.utc)
    if token_type == "refresh":
        expire_at = now + current_app.config["JWT_REFRESH_EXPIRES_DELTA"]
    else:
        expire_at = now + current_app.config["JWT_EXPIRES_DELTA"]

    payload = {
        "user_id": user.id,
        "username": user.username,
        "role": user.role,
        "token_type": token_type,
        "iat": now,
        "exp": expire_at,
    }
    token = jwt.encode(
        payload,
        current_app.config["JWT_SECRET_KEY"],
        algorithm="HS256",
    )
    if isinstance(token, bytes):
        token = token.decode("utf-8")
    return token


def decode_token(token, expected_type=None):
    """解析并校验 JWT。"""

    payload = jwt.decode(
        token,
        current_app.config["JWT_SECRET_KEY"],
        algorithms=["HS256"],
    )
    if expected_type and payload.get("token_type") != expected_type:
        raise jwt.InvalidTokenError("invalid token type")
    return payload


def get_token_from_request():
    """从 Authorization: Bearer <token> 中提取 token。"""

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    return auth_header.split(" ", 1)[1].strip()


def _load_user_from_token(expected_type):
    """校验 token 并返回当前用户或错误响应。"""

    token = get_token_from_request()
    if not token:
        return None, (jsonify({"code": 401, "message": "缺少 Bearer Token"}), 401)

    try:
        payload = decode_token(token, expected_type=expected_type)
    except jwt.ExpiredSignatureError:
        return None, (jsonify({"code": 401, "message": "登录已过期"}), 401)
    except jwt.InvalidTokenError:
        return None, (jsonify({"code": 401, "message": "无效 Token"}), 401)

    user = db.session.get(User, payload.get("user_id"))
    if not user:
        return None, (jsonify({"code": 401, "message": "用户不存在"}), 401)
    if not user.is_active:
        return None, (jsonify({"code": 403, "message": "账号已禁用"}), 403)

    g.current_user = user
    g.jwt_payload = payload
    return user, None


def login_required(view_func):
    """要求 access token 的接口装饰器。"""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        _, error_response = _load_user_from_token("access")
        if error_response:
            return error_response
        return view_func(*args, **kwargs)

    return wrapper


def refresh_token_required(view_func):
    """要求 refresh token 的接口装饰器。"""

    @wraps(view_func)
    def wrapper(*args, **kwargs):
        _, error_response = _load_user_from_token("refresh")
        if error_response:
            return error_response
        return view_func(*args, **kwargs)

    return wrapper


def role_required(*roles):
    """要求指定角色的接口装饰器。"""

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(*args, **kwargs):
            if g.current_user.role not in roles:
                return jsonify({"code": 403, "message": "权限不足"}), 403
            return view_func(*args, **kwargs)

        return wrapper

    return decorator
