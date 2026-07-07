from datetime import datetime

from flask import Blueprint, jsonify, request

from models import AlarmEvent, db

event_bp = Blueprint("event_api", __name__)


@event_bp.get("")
def list_events():
    status = request.args.get("status")
    query = AlarmEvent.query
    if status:
        query = query.filter_by(status=status)
    events = query.order_by(AlarmEvent.created_at.desc()).limit(100).all()
    return jsonify([serialize_event(event) for event in events])


@event_bp.get("/<int:event_id>")
def get_event(event_id):
    return jsonify(serialize_event(AlarmEvent.query.get_or_404(event_id)))


@event_bp.patch("/<int:event_id>/status")
def update_status(event_id):
    event = AlarmEvent.query.get_or_404(event_id)
    payload = request.get_json() or {}
    event.status = payload.get("status", event.status)
    if event.status in {"handled", "ignored"}:
        event.handled_at = datetime.utcnow()
    db.session.commit()
    return jsonify(serialize_event(event))


def serialize_event(event):
    return {
        "id": event.id,
        "type": event.alarm_type,
        "level": event.level,
        "camera_id": event.camera_id,
        "coordinate": event.coordinate,
        "status": event.status,
        "snapshot_path": event.snapshot_path,
        "created_at": event.created_at.isoformat(),
        "handled_at": event.handled_at.isoformat() if event.handled_at else None,
    }
