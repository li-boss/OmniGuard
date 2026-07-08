from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity

from models import AlarmEvent, db
from services.ws_handler import push_alarm
from services.notification_svc import push_dingtalk

event_bp = Blueprint('event_api', __name__)


@event_bp.route('', methods=['GET'])
@jwt_required()
def list_alarms():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', request.args.get('pageSize', 10, type=int), type=int)
    alarm_type = request.args.get('type', None) or request.args.get('alarm_type', None)
    severity = request.args.get('severity', None) or request.args.get('level', None)
    status = request.args.get('status', None)
    camera_id = request.args.get('camera_id', None) or request.args.get('cameraId', None)
    start_time = request.args.get('start_time', None)
    end_time = request.args.get('end_time', None)

    query = AlarmEvent.query

    if alarm_type:
        query = query.filter(AlarmEvent.alarm_type == alarm_type)
    if severity:
        query = query.filter(AlarmEvent.severity == severity)
    if status:
        if status == "handled":
            query = query.filter(AlarmEvent.status == "resolved")
        elif status == "ignored":
            query = query.filter(AlarmEvent.status == "false_positive")
        else:
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
        "code": 0,
        "message": "ok",
        "data": {
            'items': [serialize_event(a) for a in pagination.items],
            'total': pagination.total,
            'page': pagination.page,
            'per_page': pagination.per_page,
            'pages': pagination.pages,
        }
    })


@event_bp.route('/<int:alarm_id>', methods=['GET'])
@jwt_required()
def get_alarm(alarm_id):
    alarm = db.session.get(AlarmEvent, alarm_id)
    if not alarm:
        return jsonify({"code": 404, "message": "Alarm not found"}), 404
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_event(alarm)
    })


@event_bp.route('', methods=['POST'])
@jwt_required()
def create_alarm():
    data = request.get_json() or {}
    alarm_type = data.get('type') or data.get('alarm_type') or data.get('eventType') or 'intrusion'
    camera_id = data.get('camera_id') or data.get('cameraId')
    
    if not camera_id:
        return jsonify({"code": 400, "message": "Missing camera_id", "msg": "Missing field: camera_id"}), 400

    severity = data.get('severity') or data.get('level', 'medium')
    
    escalation_deadline = None
    timeout = AlarmEvent.ESCALATION_TIMEOUTS.get(0)
    if timeout:
        escalation_deadline = datetime.utcnow() + timedelta(seconds=timeout)

    alarm = AlarmEvent(
        alarm_type=alarm_type,
        severity=severity,
        camera_id=camera_id,
        zone_id=data.get('zone_id') or data.get('zoneId'),
        snapshot_url=data.get('snapshot_url') or data.get('snapshot_path') or data.get('snapshotUrl'),
        clip_url=data.get('clip_url') or data.get('clipUrl'),
        description=data.get('description'),
        detection_data=data.get('detection_data'),
        coordinate=data.get('coordinate'),
        escalation_deadline=escalation_deadline,
    )
    db.session.add(alarm)
    db.session.commit()

    push_alarm(alarm.to_dict())

    if severity in ('high', 'critical'):
        push_dingtalk(alarm, escalation_level=0)

    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_event(alarm)
    }), 201


@event_bp.route('/<int:alarm_id>/handle', methods=['PUT'])
@jwt_required()
def handle_alarm(alarm_id):
    alarm = db.session.get(AlarmEvent, alarm_id)
    if not alarm:
        return jsonify({"code": 404, "message": "Alarm not found"}), 404
    data = request.get_json() or {}

    current_user_id = get_jwt_identity()
    
    status_map = {
        "handled": "resolved",
        "ignored": "false_positive"
    }
    raw_status = data.get('status')
    if not raw_status:
        target_status = 'resolved'
    else:
        target_status = status_map.get(raw_status, raw_status)
        
    alarm.status = target_status
    alarm.handle_note = data.get('handle_note') or data.get('note', alarm.handle_note)
    alarm.handler_id = current_user_id
    alarm.handle_time = datetime.utcnow()

    if alarm.status in ('resolved', 'false_positive'):
        alarm.escalation_deadline = None

    db.session.commit()

    push_alarm(alarm.to_dict())

    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_event(alarm)
    })


@event_bp.patch("/<int:event_id>/status")
@jwt_required()
def update_status(event_id):
    event = db.session.get(AlarmEvent, event_id)
    if not event:
        return jsonify({"code": 404, "message": "Alarm not found"}), 404
    payload = request.get_json() or {}
    raw_status = payload.get("status")
    if raw_status:
        status_map = {
            "handled": "resolved",
            "ignored": "false_positive"
        }
        event.status = status_map.get(raw_status, raw_status)
        if event.status in {"resolved", "false_positive"}:
            event.handle_time = datetime.utcnow()
            event.escalation_deadline = None
    db.session.commit()
    push_alarm(event.to_dict())
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_event(event)
    })


@event_bp.route('/<int:alarm_id>/clip', methods=['GET'])
@jwt_required()
def get_alarm_clip(alarm_id):
    alarm = db.session.get(AlarmEvent, alarm_id)
    if not alarm:
        return jsonify({"code": 404, "message": "Alarm not found"}), 404
    
    clip_url = alarm.clip_url or "/static/clips/placeholder.mp4"
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            "clipUrl": clip_url,
            "clip_url": clip_url
        }
    })


def create_alarm_from_detection(detection_data):
    severity = detection_data.get('severity', 'medium')
    escalation_deadline = None
    timeout = AlarmEvent.ESCALATION_TIMEOUTS.get(0)
    if timeout:
        escalation_deadline = datetime.utcnow() + timedelta(seconds=timeout)

    alarm = AlarmEvent(
        alarm_type=detection_data.get('type') or detection_data.get('alarm_type', 'intrusion'),
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


def serialize_event(event):
    status_map = {
        "resolved": "handled",
        "false_positive": "ignored"
    }
    frontend_status = status_map.get(event.status, event.status)
    
    return {
        "id": event.id,
        "cameraId": event.camera_id,
        "camera_id": event.camera_id,
        "zoneId": event.zone_id or 1,
        "zone_id": event.zone_id or 1,
        
        "eventType": event.type,
        "alarm_type": event.type,
        "type": event.type,
        
        "severity": event.severity,
        "level": event.severity,
        
        "status": frontend_status,
        "confidence": 0.95,
        
        "snapshotUrl": event.snapshot_url,
        "snapshot_url": event.snapshot_url,
        "snapshot_path": event.snapshot_url,
        
        "occurredAt": event.created_at.isoformat() + 'Z' if event.created_at else None,
        "created_at": event.created_at.isoformat() + 'Z' if event.created_at else None,
        "handledAt": event.handle_time.isoformat() + 'Z' if event.handle_time else None,
        "handle_time": event.handle_time.isoformat() + 'Z' if event.handle_time else None,
        
        "title": f"围栏入侵 - 摄像头 {event.camera_id}",
        "description": event.description or f"目标触发 {event.type} 规则",
        
        "clip_url": event.clip_url,
        "clipUrl": event.clip_url,
        "handler_id": event.handler_id,
        "handle_note": event.handle_note,
        "escalation_level": event.escalation_level,
        "escalation_deadline": event.escalation_deadline.isoformat() if event.escalation_deadline else None,
        "dingtalk_notified": event.dingtalk_notified,
    }
