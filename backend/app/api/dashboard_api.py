from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app

from ..middleware.auth_middleware import auth_required
from ..models import AlarmEvent, FaceRecord, Zone
from . import success


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.get("/summary")
@auth_required
def summary():
    now = datetime.now(timezone.utc)
    recent_alarms = AlarmEvent.query.order_by(AlarmEvent.occurred_at.desc()).limit(5).all()
    all_alarms = AlarmEvent.query.all()
    severity_counter = Counter(alarm.severity for alarm in all_alarms)

    trend = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        count = sum(1 for alarm in all_alarms if alarm.occurred_at.date() == day)
        trend.append({"date": day.isoformat(), "count": count})

    return success({
        "cameraCount": 1,
        "zoneCount": Zone.query.count(),
        "faceCount": FaceRecord.query.count(),
        "alarmCount": AlarmEvent.query.count(),
        "pendingAlarmCount": AlarmEvent.query.filter_by(status="pending").count(),
        "rtmpBaseUrl": current_app.config["RTMP_BASE_URL"],
        "videoFeedUrl": current_app.config["VIDEO_FEED_URL"],
        "severity": dict(severity_counter),
        "trend": trend,
        "recentAlarms": [alarm.to_dict() for alarm in recent_alarms],
    })
