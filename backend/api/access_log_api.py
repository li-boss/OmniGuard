from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from models import AccessLog, db

access_log_bp = Blueprint('access_log', __name__, url_prefix='/api/access-logs')


@access_log_bp.route('', methods=['GET'])
@jwt_required()
def list_access_logs():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', request.args.get('pageSize', 20, type=int), type=int)
    user_id = request.args.get('user_id', None)
    zone_id = request.args.get('zone_id', None)
    access_method = request.args.get('access_method', None)
    result = request.args.get('result', None)
    device_code = request.args.get('device_code', None)
    start_time = request.args.get('start_time', None)
    end_time = request.args.get('end_time', None)

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
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            'items': [log.to_dict() for log in pagination.items],
            'total': pagination.total,
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages,
        }
    })


@access_log_bp.route('/<int:log_id>', methods=['GET'])
@jwt_required()
def get_access_log(log_id):
    log = db.session.get(AccessLog, log_id)
    if not log:
        return jsonify({"code": 404, "message": "Access log not found"}), 404
    
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": log.to_dict()
    })


@access_log_bp.route('/<int:log_id>', methods=['DELETE'])
@jwt_required()
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