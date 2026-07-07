"""
人脸管理 API。

对应 IFace：
- POST /api/faces/register
- GET /api/faces
- DELETE /api/faces/<id>
"""

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from backend.middleware.auth_middleware import login_required, role_required
from backend.models import Face, User, db


face_bp = Blueprint("face_api", __name__)


def _json():
    return request.get_json(silent=True) or {}


def _success(data=None, message="ok", status=200):
    return jsonify({"code": status, "message": message, "data": data or {}}), status


def _error(message, status):
    return jsonify({"code": status, "message": message, "data": {}}), status


def _is_privileged(user):
    return user.role in ("admin", "security")


def _can_manage_face(user, user_id):
    return _is_privileged(user) or user.id == user_id


@face_bp.post("/api/faces/register")
@login_required
def register_face():
    """注册人脸。管理员/安全员可为任意用户注册，普通用户只能为自己注册。"""

    data = _json()
    user_id = data.get("user_id")
    feature_data = data.get("feature_data") or data.get("face_encoding")

    if not user_id or not feature_data:
        return _error("user_id 和 feature_data 不能为空", 400)
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return _error("user_id 格式错误", 400)
    if not _can_manage_face(g.current_user, user_id):
        return _error("权限不足", 403)

    user = db.session.get(User, user_id)
    if not user:
        return _error("用户不存在", 404)

    face = Face(
        user_id=user_id,
        image_path=data.get("image_path") or data.get("face_image_url"),
        feature_data=feature_data,
        device_code=data.get("device_code"),
        status=data.get("status", "active"),
    )
    db.session.add(face)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("人脸注册失败", 500)

    return _success({"face": face.to_dict()}, "人脸注册成功", 201)


@face_bp.get("/api/faces")
@login_required
def list_faces():
    """查询人脸列表。普通用户只能查询自己的人脸。"""

    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    user_id = request.args.get("user_id", type=int)
    include_feature = request.args.get("include_feature", "0") == "1"

    if not _is_privileged(g.current_user):
        if user_id and user_id != g.current_user.id:
            return _error("权限不足", 403)
        user_id = g.current_user.id
        include_feature = False

    query = Face.query
    if user_id:
        query = query.filter_by(user_id=user_id)

    pagination = query.order_by(Face.id.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    return _success(
        {
            "items": [
                face.to_dict(include_feature=include_feature)
                for face in pagination.items
            ],
            "total": pagination.total,
            "page": page,
            "page_size": page_size,
        }
    )


@face_bp.get("/api/faces/features")
@role_required("admin", "security")
def list_active_face_features():
    """查询可用于 D 模块识别的人脸特征库。"""

    faces = Face.query.filter_by(status="active").order_by(Face.id.asc()).all()
    return _success({"items": [face.to_dict(include_feature=True) for face in faces]})


@face_bp.delete("/api/faces/<int:face_id>")
@login_required
def delete_face(face_id):
    """删除人脸。管理员/安全员可删除任意人脸，普通用户只能删除自己的。"""

    face = db.session.get(Face, face_id)
    if not face:
        return _error("人脸不存在", 404)
    if not _can_manage_face(g.current_user, face.user_id):
        return _error("权限不足", 403)

    db.session.delete(face)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return _error("人脸删除失败", 500)

    return _success(message="人脸删除成功")
