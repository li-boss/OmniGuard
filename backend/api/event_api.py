from datetime import datetime
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.app import db
from backend.models.alarm import AlarmEvent
from backend.services.ws_handler import push_alarm
from backend.services.notification_svc import push_dingtalk, check_escalation

event_bp = Blueprint('event', __name__, url_prefix='/api/alarms')


@event_bp.route('', methods=['GET'])
@jwt_required()
def list_alarms():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    alarm_type = request.args.get('type', None)
    severity = request.args.get('severity', None)
    status = request.args.get('status', None)
    camera_id = request.args.get('camera_id', None)
    start_time = request.args.get('start_time', None)
    end_time = request.args.get('end_time', None)

    query = AlarmEvent.query

    if alarm_type:
        query = query.filter(AlarmEvent.type == alarm_type)
    if severity:
        query = query.filter(AlarmEvent.severity == severity)
    if status:
        query = query.filter(AlarmEvent.status == status)
    if camera_id:
        query = query.filter(AlarmEvent.camera_id == camera_id)
    if start_time:
        query = query.filter(AlarmEvent.created_at >= datetime.fromisoformat(start_time))
    if end_time:
        query = query.filter(AlarmEvent.created_at <= datetime.fromisoformat(end_time))

    query = query.order_by(AlarmEvent.created_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'items': [a.to_dict() for a in pagination.items],
        'total': pagination.total,
        'page': pagination.page,
        'per_page': pagination.per_page,
        'pages': pagination.pages,
    })


@event_bp.route('/<int:alarm_id>', methods=['GET'])
@jwt_required()
def get_alarm(alarm_id):
    alarm = AlarmEvent.query.get_or_404(alarm_id)
    return jsonify(alarm.to_dict())


@event_bp.route('', methods=['POST'])
@jwt_required()
def create_alarm():
    data = request.get_json()
    if not data:
        return jsonify({'msg': 'No input data'}), 400

    required_fields = ['type', 'camera_id']
    for f in required_fields:
        if f not in data:
            return jsonify({'msg': f'Missing field: {f}'}), 400

    severity = data.get('severity', 'medium')
    escalation_deadline = None
    timeout = AlarmEvent.ESCALATION_TIMEOUTS.get(0)
    if timeout:
        from datetime import timedelta
        escalation_deadline = datetime.utcnow() + timedelta(seconds=timeout)

    alarm = AlarmEvent(
        type=data['type'],
        severity=severity,
        camera_id=data['camera_id'],
        zone_id=data.get('zone_id'),
        snapshot_url=data.get('snapshot_url'),
        description=data.get('description'),
        detection_data=data.get('detection_data'),
        escalation_deadline=escalation_deadline,
    )
    db.session.add(alarm)
    db.session.commit()

    push_alarm(alarm.to_dict())

    if severity in ('high', 'critical'):
        push_dingtalk(alarm, escalation_level=0)

    return jsonify(alarm.to_dict()), 201


@event_bp.route('/<int:alarm_id>/handle', methods=['PUT'])
@jwt_required()
def handle_alarm(alarm_id):
    alarm = AlarmEvent.query.get_or_404(alarm_id)
    data = request.get_json()
    if not data:
        return jsonify({'msg': 'No input data'}), 400

    current_user_id = get_jwt_identity()
    alarm.status = data.get('status', alarm.status)
    alarm.handle_note = data.get('handle_note', alarm.handle_note)
    alarm.handler_id = current_user_id
    alarm.handle_time = datetime.utcnow()

    if alarm.status in ('resolved', 'false_positive'):
        alarm.escalation_deadline = None

    db.session.commit()

    push_alarm(alarm.to_dict())

    return jsonify(alarm.to_dict())


@event_bp.route('/<int:alarm_id>/clip', methods=['GET'])
@jwt_required()
def get_alarm_clip(alarm_id):
    alarm = AlarmEvent.query.get_or_404(alarm_id)
    if not alarm.clip_url:
        return jsonify({'msg': 'No clip available'}), 404
    return jsonify({'clip_url': alarm.clip_url})


def create_alarm_from_detection(detection_data):
    severity = detection_data.get('severity', 'medium')
    escalation_deadline = None
    timeout = AlarmEvent.ESCALATION_TIMEOUTS.get(0)
    if timeout:
        from datetime import timedelta
        escalation_deadline = datetime.utcnow() + timedelta(seconds=timeout)

    alarm = AlarmEvent(
        type=detection_data.get('type', 'intrusion'),
        severity=severity,
        camera_id=detection_data['camera_id'],
        zone_id=detection_data.get('zone_id'),
        snapshot_url=detection_data.get('snapshot_url'),
        description=detection_data.get('description'),
        detection_data=detection_data.get('detection_data'),
        escalation_deadline=escalation_deadline,
    )
    db.session.add(alarm)
    db.session.commit()

    push_alarm(alarm.to_dict())

    if severity in ('high', 'critical'):
        push_dingtalk(alarm, escalation_level=0)

    return alarm
