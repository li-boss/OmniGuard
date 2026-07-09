from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app
from sqlalchemy import func

from ..extensions import db
from ..middleware.auth_middleware import auth_required
from ..models import AlarmEvent, FaceRecord, Zone
from . import success


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/summary")
@auth_required
def summary():
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)

    recent_alarms = AlarmEvent.query.order_by(AlarmEvent.occurred_at.desc()).limit(5).all()
    all_alarms = AlarmEvent.query.all()
    severity_counter = Counter(alarm.severity for alarm in all_alarms)
    type_counter = Counter(alarm.event_type for alarm in all_alarms)

    trend = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        count = sum(1 for alarm in all_alarms if alarm.occurred_at.date() == day)
        trend.append({"date": day.isoformat(), "count": count})

    camera_stats = (
        db.session.query(AlarmEvent.camera_id, func.count(AlarmEvent.id))
        .group_by(AlarmEvent.camera_id)
        .order_by(func.count(AlarmEvent.id).desc())
        .limit(10)
        .all()
    )
    hour_distribution = []
    for hour in range(24):
        count = sum(1 for alarm in all_alarms if alarm.occurred_at.hour == hour)
        hour_distribution.append({"hour": hour, "count": count})

    total_alarms = AlarmEvent.query.count()
    pending_alarms = AlarmEvent.query.filter_by(status="pending").count()
    handling_alarms = AlarmEvent.query.filter_by(status="handling").count()
    resolved_today = AlarmEvent.query.filter(
        AlarmEvent.status.in_(["handled", "resolved"]),
        AlarmEvent.handled_at >= today_start,
    ).count()
    today_alarms = AlarmEvent.query.filter(AlarmEvent.occurred_at >= today_start).count()
    week_alarms = AlarmEvent.query.filter(AlarmEvent.occurred_at >= week_ago).count()

    return success({
        "cameraCount": 1,
        "zoneCount": Zone.query.count(),
        "faceCount": FaceRecord.query.count(),
        "alarmCount": total_alarms,
        "pendingAlarmCount": pending_alarms,
        "rtmpBaseUrl": current_app.config["RTMP_BASE_URL"],
        "videoFeedUrl": current_app.config["VIDEO_FEED_URL"],
        "severity": dict(severity_counter),
        "trend": trend,
        "recentAlarms": [alarm.to_dict() for alarm in recent_alarms],
        "total_alarms": total_alarms,
        "pending_alarms": pending_alarms,
        "handling_alarms": handling_alarms,
        "resolved_today": resolved_today,
        "today_alarms": today_alarms,
        "week_alarms": week_alarms,
        "severity_distribution": dict(severity_counter),
        "type_distribution": dict(type_counter),
        "trend_7days": trend,
        "camera_top10": [{"camera_id": camera_id, "count": count} for camera_id, count in camera_stats],
        "hour_distribution": hour_distribution,
    })
