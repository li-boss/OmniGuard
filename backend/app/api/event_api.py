from datetime import datetime, timezone

from flask import Blueprint, g, request

from ..extensions import db
from ..middleware.auth_middleware import auth_required
from ..models import AlarmEvent
from ..services.notification_svc import check_escalation
from ..services.ws_handler import push_alarm
from . import error, success


alarm_bp = Blueprint("alarms", __name__)


def create_alarm(payload, push=True):
    alarm = AlarmEvent(
        camera_id=str(payload.get("cameraId") or payload.get("camera_id") or "default"),
        zone_id=payload.get("zoneId") or payload.get("zone_id"),
        event_type=str(payload.get("eventType") or payload.get("event_type") or "intrusion"),
        title=str(payload.get("title") or "围栏入侵"),
        description=payload.get("description"),
        severity=str(payload.get("severity") or "medium"),
        confidence=payload.get("confidence"),
        snapshot_url=payload.get("snapshotUrl") or payload.get("snapshot_url"),
        clip_url=payload.get("clipUrl") or payload.get("clip_url"),
    )
    db.session.add(alarm)
    db.session.commit()
    data = alarm.to_dict()
    if push:
        push_alarm(data)
        check_escalation(alarm.id)
    return alarm


@alarm_bp.get("")
@auth_required
def list_alarms():
    page = max(int(request.args.get("page", "1")), 1)
    page_size = min(max(int(request.args.get("pageSize", "10")), 1), 100)
    query = AlarmEvent.query

    for arg, column in (
        ("type", AlarmEvent.event_type),
        ("severity", AlarmEvent.severity),
        ("status", AlarmEvent.status),
    ):
        value = request.args.get(arg)
        if value:
            query = query.filter(column == value)

    total = query.count()
    alarms = (
        query.order_by(AlarmEvent.occurred_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return success({
        "items": [alarm.to_dict() for alarm in alarms],
        "page": page,
        "pageSize": page_size,
        "total": total,
    })


@alarm_bp.post("")
@auth_required
def simulate_alarm():
    payload = request.get_json(silent=True) or {}
    alarm = create_alarm(payload)
    return success(alarm.to_dict(), "alarm created", 201)


@alarm_bp.put("/<int:alarm_id>/handle")
@auth_required
def handle_alarm(alarm_id):
    alarm = db.get_or_404(AlarmEvent, alarm_id)
    payload = request.get_json(silent=True) or {}
    note = str(payload.get("note") or "").strip()
    alarm.mark_handled(g.current_user.username, note)
    db.session.commit()
    push_alarm({
        "type": "alarm_handled",
        "alarm": alarm.to_dict(),
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    return success(alarm.to_dict(), "alarm handled")


@alarm_bp.get("/<int:alarm_id>/clip")
@auth_required
def alarm_clip(alarm_id):
    alarm = db.get_or_404(AlarmEvent, alarm_id)
    return success({
        "alarmId": alarm.id,
        "clipUrl": alarm.clip_url,
        "snapshotUrl": alarm.snapshot_url,
    })
