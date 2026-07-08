from datetime import datetime

from flask import Blueprint, jsonify, request

from models import AlarmEvent, db

event_bp = Blueprint("event_api", __name__)


@event_bp.get("")
def list_events():
    status = request.args.get("status")
    severity = request.args.get("severity") or request.args.get("level")
    camera_id = request.args.get("camera_id") or request.args.get("cameraId")
    
    query = AlarmEvent.query
    if status:
        query = query.filter_by(status=status)
    if severity:
        query = query.filter_by(level=severity)
    if camera_id:
        query = query.filter_by(camera_id=camera_id)
        
    # Get pagination parameters from query string
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("pageSize") or request.args.get("page_size", 10))
    
    # Calculate count
    total = query.count()
    
    # Pagination
    events = query.order_by(AlarmEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            "items": [serialize_event(event) for event in events],
            "total": total
        }
    })


@event_bp.get("/<int:event_id>")
def get_event(event_id):
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_event(AlarmEvent.query.get_or_404(event_id))
    })


@event_bp.patch("/<int:event_id>/status")
def update_status(event_id):
    event = AlarmEvent.query.get_or_404(event_id)
    payload = request.get_json() or {}
    event.status = payload.get("status", event.status)
    if event.status in {"handled", "ignored"}:
        event.handled_at = datetime.utcnow()
    db.session.commit()
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_event(event)
    })


@event_bp.put("/<int:event_id>/handle")
def handle_event(event_id):
    event = AlarmEvent.query.get_or_404(event_id)
    payload = request.get_json() or {}
    event.status = "handled"
    event.handled_at = datetime.utcnow()
    db.session.commit()
    
    # Also broadcast handled event status via websocket
    try:
        from services.ws_handler import emit_alarm
        payload = serialize_event(event)
        payload["type"] = "alarm_handled"
        emit_alarm(payload)
    except Exception:
        pass
        
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_event(event)
    })


@event_bp.post("")
def simulate_alarm():
    payload = request.get_json() or {}
    event = AlarmEvent(
        alarm_type=payload.get("eventType") or payload.get("alarm_type", "intrusion"),
        level=payload.get("severity") or payload.get("level", "high"),
        camera_id=payload.get("cameraId") or payload.get("camera_id", "cam-1"),
        coordinate={"person_box": [0.2, 0.3, 0.4, 0.5]},
        status="pending",
        snapshot_path="/static/snapshots/placeholder.jpg",
        created_at=datetime.utcnow()
    )
    db.session.add(event)
    db.session.commit()
    
    # Broadcast via WebSocket
    try:
        from services.ws_handler import emit_alarm
        emit_alarm(serialize_event(event))
    except Exception:
        pass
        
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": serialize_event(event)
    }), 201


def serialize_event(event):
    return {
        "id": event.id,
        "cameraId": event.camera_id,
        "camera_id": event.camera_id,
        "zoneId": 1,
        "eventType": event.alarm_type,
        "alarm_type": event.alarm_type,
        "title": f"围栏入侵 - 摄像头 {event.camera_id}",
        "description": f"目标触发 {event.alarm_type} 规则",
        "severity": event.level,
        "level": event.level,
        "status": event.status,
        "confidence": 0.95,
        "snapshotUrl": event.snapshot_path,
        "snapshot_path": event.snapshot_path,
        "occurredAt": event.created_at.isoformat() + 'Z',
        "created_at": event.created_at.isoformat() + 'Z',
        "handledAt": event.handled_at.isoformat() + 'Z' if event.handled_at else None,
    }
