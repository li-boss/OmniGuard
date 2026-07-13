import logging
from datetime import datetime, timezone

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from middleware.auth_middleware import login_required, role_required
from models import AccessLog, User, AlertZone, db

logger = logging.getLogger(__name__)

log_bp = Blueprint("log_api", __name__)

def _json():
    return request.get_json(silent=True) or {}

def _success(data=None, message="ok", status=200):
    return jsonify({"code": 0, "message": message, "data": data if data is not None else {}}), status

def _error(message, status):
    return jsonify({"code": 1, "message": message, "data": None}), status

def _parse_datetime(value):
    """解析 ISO 时间字符串。"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None

@log_bp.get("/api/access-logs")
@login_required
def list_access_logs():
    """分页查询通行日志。"""
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("page_size", 20, type=int)
    user_id = request.args.get("user_id", type=int)
    zone_id = request.args.get("zone_id", type=int)
    result = request.args.get("result")

    # 权限检查：非特权用户只能查询自己的通行记录
    if g.current_user.role not in ("admin", "security"):
        if user_id and user_id != g.current_user.id:
            return _error("权限不足", 403)
        user_id = g.current_user.id

    query = AccessLog.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if zone_id:
        query = query.filter_by(zone_id=zone_id)
    if result:
        query = query.filter_by(result=result)

    pagination = query.order_by(AccessLog.occurred_at.desc()).paginate(
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

@log_bp.post("/api/access-logs")
@role_required("admin", "security")
def create_access_log():
    """写入通行日志。"""
    data = _json()
    zone_id = data.get("zone_id")
    user_id = data.get("user_id")

    if not zone_id:
        return _error("zone_id 不能为空", 400)
    
    if user_id and not db.session.get(User, user_id):
        return _error("用户不存在", 404)
        
    if not db.session.get(AlertZone, zone_id):
        return _error("防区不存在", 404)

    access_log = AccessLog(
        user_id=user_id,
        zone_id=zone_id,
        access_method=data.get("access_method", "face"),
        direction=data.get("direction", "in"),
        result=data.get("result", "granted"),
        device_code=data.get("device_code"),
        confidence=data.get("confidence"),
        remark=data.get("remark"),
        occurred_at=_parse_datetime(data.get("occurred_at")) or datetime.now(timezone.utc),
    )
    
    db.session.add(access_log)
    try:
        db.session.commit()
    except SQLAlchemyError as se:
        db.session.rollback()
        logger.error(f"Failed to record access log: {se}")
        return _error("通行日志写入失败", 500)

    return _success({"log": access_log.to_dict()}, "通行日志已记录", 201)
