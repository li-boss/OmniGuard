from datetime import datetime, timedelta, timezone
from collections import Counter

from flask import Blueprint, jsonify

from models import AlarmEvent, AlertZone, RegisteredFace
from api.event_api import serialize_event

dashboard_bp = Blueprint("dashboard_api", __name__)


@dashboard_bp.get("/summary")
def summary():
    from core_cv.pipeline import CameraPipelineManager
    
    # 1. Fetch camera count from pipeline manager
    try:
        manager = CameraPipelineManager()
        camera_count = max(1, len(manager.pipelines))
    except Exception:
        camera_count = 1
        
    # 2. Get counts from SQLite database
    zone_count = AlertZone.query.count()
    face_count = RegisteredFace.query.count()
    alarm_count = AlarmEvent.query.count()
    pending_alarm_count = AlarmEvent.query.filter_by(status="pending").count()
    
    # 3. Get recent 5 alarms
    recent_alarms = AlarmEvent.query.order_by(AlarmEvent.created_at.desc()).limit(5).all()
    
    # 4. Get 7-day trend
    now = datetime.utcnow()
    trend = []
    for offset in range(6, -1, -1):
        day = (now - timedelta(days=offset)).date()
        count = AlarmEvent.query.filter(
            AlarmEvent.created_at >= datetime.combine(day, datetime.min.time()),
            AlarmEvent.created_at <= datetime.combine(day, datetime.max.time()),
        ).count()
        trend.append({"date": day.isoformat(), "count": count})
        
    # 5. Severity distribution
    severity_counter = Counter(alarm.level for alarm in AlarmEvent.query.all())
    
    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            "cameraCount": camera_count,
            "zoneCount": zone_count,
            "faceCount": face_count,
            "alarmCount": alarm_count,
            "pendingAlarmCount": pending_alarm_count,
            "rtmpBaseUrl": "rtmp://127.0.0.1:1935/live",
            "videoFeedUrl": "0",  # Default camera index
            "severity": dict(severity_counter),
            "trend": trend,
            "recentAlarms": [serialize_event(alarm) for alarm in recent_alarms],
        }
    })
