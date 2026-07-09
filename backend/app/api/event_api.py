from datetime import datetime, timedelta, timezone

from flask import Blueprint, g, request

from ..extensions import db
from ..middleware.auth_middleware import auth_required
from ..models import AlarmEvent
from ..services.notification_svc import check_escalation, push_dingtalk
from ..services.ws_handler import push_alarm
from . import success


alarm_bp = Blueprint("alarms", __name__)


def _parse_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _initial_escalation_deadline(severity):
    if severity not in {"high", "critical"}:
        return None
    timeout = AlarmEvent.ESCALATION_TIMEOUTS.get(1, 600)
    return datetime.now(timezone.utc) + timedelta(seconds=timeout)


def create_alarm(payload, push=True):
    severity = str(payload.get("severity") or "medium")
    event_type = str(payload.get("eventType") or payload.get("event_type") or payload.get("type") or "intrusion")
    alarm = AlarmEvent(
        camera_id=str(payload.get("cameraId") or payload.get("camera_id") or "default"),
        zone_id=payload.get("zoneId") or payload.get("zone_id"),
        event_type=event_type,
        title=str(payload.get("title") or event_type),
        description=payload.get("description"),
        severity=severity,
        confidence=payload.get("confidence"),
        snapshot_url=payload.get("snapshotUrl") or payload.get("snapshot_url"),
        clip_url=payload.get("clipUrl") or payload.get("clip_url"),
        detection_data=payload.get("detectionData") or payload.get("detection_data"),
        escalation_deadline=_initial_escalation_deadline(severity),
    )
    db.session.add(alarm)
    db.session.commit()
    data = alarm.to_dict()
    if push:
        push_alarm(data)
        if severity in {"high", "critical"}:
            push_dingtalk(alarm, escalation_level=0)
        check_escalation(alarm.id)
    return alarm


def create_alarm_from_detection(detection_data):
    return create_alarm(detection_data)


@alarm_bp.get("")
@auth_required
def list_alarms():
    page = max(int(request.args.get("page", "1")), 1)
    page_size = min(max(int(request.args.get("pageSize") or request.args.get("per_page") or "10"), 1), 100)
    query = AlarmEvent.query

    for arg, column in (
        ("type", AlarmEvent.event_type),
        ("eventType", AlarmEvent.event_type),
        ("severity", AlarmEvent.severity),
        ("status", AlarmEvent.status),
        ("camera_id", AlarmEvent.camera_id),
        ("cameraId", AlarmEvent.camera_id),
    ):
        value = request.args.get(arg)
        if value:
            query = query.filter(column == value)

    start_time = _parse_datetime(request.args.get("start_time") or request.args.get("startTime"))
    end_time = _parse_datetime(request.args.get("end_time") or request.args.get("endTime"))
    if start_time:
        query = query.filter(AlarmEvent.occurred_at >= start_time)
    if end_time:
        query = query.filter(AlarmEvent.occurred_at <= end_time)

    pagination = query.order_by(AlarmEvent.occurred_at.desc()).paginate(
        page=page,
        per_page=page_size,
        error_out=False,
    )
    return success({
        "items": [alarm.to_dict() for alarm in pagination.items],
        "page": pagination.page,
        "pageSize": pagination.per_page,
        "per_page": pagination.per_page,
        "pages": pagination.pages,
        "total": pagination.total,
    })


@alarm_bp.post("")
@auth_required
def simulate_alarm():
    payload = request.get_json(silent=True) or {}
    alarm = create_alarm(payload)
    return success(alarm.to_dict(), "alarm created", 201)


@alarm_bp.get("/<int:alarm_id>")
@auth_required
def get_alarm(alarm_id):
    alarm = db.get_or_404(AlarmEvent, alarm_id)
    return success(alarm.to_dict())


@alarm_bp.put("/<int:alarm_id>/handle")
@auth_required
def handle_alarm(alarm_id):
    alarm = db.get_or_404(AlarmEvent, alarm_id)
    payload = request.get_json(silent=True) or {}
    status = str(payload.get("status") or "handled")
    note = str(payload.get("note") or payload.get("handle_note") or "").strip()
    if status in {"handled", "resolved", "false_positive"}:
        alarm.mark_handled(g.current_user.username, note)
        alarm.status = status
    else:
        alarm.status = status
        alarm.handle_note = note
    alarm.handler_id = g.current_user.id
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
        "alarm_id": alarm.id,
        "clipUrl": alarm.clip_url,
        "clip_url": alarm.clip_url,
        "snapshotUrl": alarm.snapshot_url,
        "snapshot_url": alarm.snapshot_url,
    })
