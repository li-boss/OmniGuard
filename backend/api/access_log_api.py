import logging
from datetime import datetime

from flask import Blueprint, g, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from middleware.auth_middleware import login_required, role_required
from models import AccessLog, AlertZone, User, db


logger = logging.getLogger(__name__)

access_log_bp = Blueprint('access_log', __name__, url_prefix='/api/access-logs')


@access_log_bp.route('', methods=['GET'])
@login_required
def list_access_logs():
    page = request.args.get('page', 1, type=int)
    page_size = request.args.get('pageSize', type=int)
    if page_size is None:
        page_size = request.args.get('per_page', type=int)
    if page_size is None:
        page_size = request.args.get('page_size', 20, type=int)
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    user_id = request.args.get('user_id', type=int)
    zone_id = request.args.get('zone_id', type=int)
    access_method = request.args.get('access_method', None)
    result = request.args.get('result', None)
    device_code = request.args.get('device_code', None)
    start_time = request.args.get('start_time', None)
    end_time = request.args.get('end_time', None)

    if g.current_user.role not in ('admin', 'security'):
        if user_id and user_id != g.current_user.id:
            return jsonify({"code": 1, "message": "权限不足", "data": None}), 403
        user_id = g.current_user.id

    query = AccessLog.query

    if user_id:
        query = query.filter(AccessLog.user_id == user_id)
    if zone_id:
        query = query.filter(AccessLog.zone_id == zone_id)
    if access_method:
        query = query.filter(AccessLog.access_method == access_method)
    if result:
        query = query.filter(AccessLog.result == result)
    if device_code:
        query = query.filter(AccessLog.device_code == device_code)
    if start_time:
        query = query.filter(AccessLog.occurred_at >= datetime.fromisoformat(start_time))
    if end_time:
        query = query.filter(AccessLog.occurred_at <= datetime.fromisoformat(end_time))

    query = query.order_by(AccessLog.occurred_at.desc())
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            'items': [log.to_dict() for log in pagination.items],
            'total': pagination.total,
            'page': pagination.page,
            'pageSize': pagination.per_page,
            'page_size': pagination.per_page,
            'per_page': pagination.per_page,
            'pages': pagination.pages,
        }
    })


@access_log_bp.route('', methods=['POST'])
@role_required('admin', 'security')
def create_access_log():
    data = request.get_json(silent=True) or {}
    zone_id = data.get('zone_id')
    user_id = data.get('user_id')

    if not zone_id:
        return jsonify({"code": 1, "message": "zone_id 不能为空", "data": None}), 400
    if user_id and not db.session.get(User, user_id):
        return jsonify({"code": 1, "message": "用户不存在", "data": None}), 404
    if not db.session.get(AlertZone, zone_id):
        return jsonify({"code": 1, "message": "防区不存在", "data": None}), 404

    occurred_at = None
    if data.get('occurred_at'):
        try:
            occurred_at = datetime.fromisoformat(data['occurred_at'])
        except ValueError:
            return jsonify({"code": 1, "message": "occurred_at 格式无效", "data": None}), 400

    access_log = AccessLog(
        user_id=user_id,
        zone_id=zone_id,
        access_method=data.get('access_method', 'face'),
        direction=data.get('direction', 'in'),
        result=data.get('result', 'granted'),
        device_code=data.get('device_code'),
        confidence=data.get('confidence'),
        remark=data.get('remark'),
        occurred_at=occurred_at or datetime.now(),
    )
    db.session.add(access_log)
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error("Failed to record access log: %s", exc)
        return jsonify({"code": 1, "message": "通行日志写入失败", "data": None}), 500

    return jsonify({
        "code": 0,
        "message": "通行日志已记录",
        "data": {"log": access_log.to_dict()},
    }), 201


@access_log_bp.route('/<int:log_id>', methods=['GET'])
@login_required
def get_access_log(log_id):
    log = db.session.get(AccessLog, log_id)
    if not log:
        return jsonify({"code": 404, "message": "Access log not found"}), 404
    if g.current_user.role not in ('admin', 'security') and log.user_id != g.current_user.id:
        return jsonify({"code": 1, "message": "权限不足", "data": None}), 403
    
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": log.to_dict()
    })


@access_log_bp.route('/<int:log_id>', methods=['DELETE'])
@role_required('admin', 'security')
def delete_access_log(log_id):
    log = db.session.get(AccessLog, log_id)
    if not log:
        return jsonify({"code": 404, "message": "Access log not found"}), 404
    
    db.session.delete(log)
    db.session.commit()
    
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": None
    })
