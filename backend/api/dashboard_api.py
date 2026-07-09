from datetime import datetime, timedelta
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from models import AlarmEvent, AlertZone, RegisteredFace, db
from api.event_api import serialize_event

dashboard_bp = Blueprint('dashboard_api', __name__)


@dashboard_bp.route('/summary', methods=['GET'])
@jwt_required()
def get_summary():
    # 1. Fetch camera count from CameraPipelineManager
    from core_cv.pipeline import CameraPipelineManager
    try:
        manager = CameraPipelineManager()
        camera_count = max(1, len(manager.pipelines))
    except Exception:
        camera_count = 1

    # 2. Get counts from SQLite database
    zone_count = AlertZone.query.count()
    face_count = RegisteredFace.query.count()
    total_alarms = AlarmEvent.query.count()
    pending_alarms = AlarmEvent.query.filter(AlarmEvent.status == 'pending').count()
    handling_alarms = AlarmEvent.query.filter(AlarmEvent.status == 'handling').count()

    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    resolved_today = AlarmEvent.query.filter(
        AlarmEvent.status == 'resolved',
        AlarmEvent.handle_time >= today_start,
    ).count()

    today_alarms = AlarmEvent.query.filter(
        AlarmEvent.created_at >= today_start,
    ).count()
    week_alarms = AlarmEvent.query.filter(
        AlarmEvent.created_at >= week_ago,
    ).count()

    # 3. Severity stats
    severity_stats = db.session.query(
        AlarmEvent.severity, func.count(AlarmEvent.id)
    ).group_by(AlarmEvent.severity).all()
    severity_distribution = {s: c for s, c in severity_stats}

    # 4. Type stats
    type_stats = db.session.query(
        AlarmEvent.alarm_type, func.count(AlarmEvent.id)
    ).group_by(AlarmEvent.alarm_type).all()
    type_distribution = {t: c for t, c in type_stats}

    # 5. Trend data
    trend_data_e = []
    trend_data_b = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = AlarmEvent.query.filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
        ).count()
        trend_data_e.append({
            'date': day_start.strftime('%Y-%m-%d'),
            'count': count,
        })
        trend_data_b.append({
            'date': day_start.date().isoformat(),
            'count': count,
        })

    # 6. Top cameras
    camera_stats = db.session.query(
        AlarmEvent.camera_id, func.count(AlarmEvent.id)
    ).group_by(AlarmEvent.camera_id).order_by(func.count(AlarmEvent.id).desc()).limit(10).all()
    camera_distribution = [{'camera_id': c, 'count': cnt} for c, cnt in camera_stats]

    # 7. Hour distribution
    hour_distribution = []
    for h in range(24):
        count = AlarmEvent.query.filter(
            func.extract('hour', AlarmEvent.created_at) == h
        ).count()
        hour_distribution.append({'hour': h, 'count': count})

    # 8. Recent 5 alarms
    recent_alarms = AlarmEvent.query.order_by(AlarmEvent.created_at.desc()).limit(5).all()

    return jsonify({
        "code": 0,
        "message": "ok",
        "data": {
            # B's expected fields
            "cameraCount": camera_count,
            "zoneCount": zone_count,
            "faceCount": face_count,
            "alarmCount": total_alarms,
            "pendingAlarmCount": pending_alarms,
            "rtmpBaseUrl": "rtmp://127.0.0.1:1935/live",
            "videoFeedUrl": "/api/streams/demo.mjpg",
            "severity": severity_distribution,
            "trend": trend_data_b,
            "recentAlarms": [serialize_event(alarm) for alarm in recent_alarms],
            
            # E's expected fields
            "total_alarms": total_alarms,
            "pending_alarms": pending_alarms,
            "handling_alarms": handling_alarms,
            "resolved_today": resolved_today,
            "today_alarms": today_alarms,
            "week_alarms": week_alarms,
            "severity_distribution": severity_distribution,
            "type_distribution": type_distribution,
            "trend_7days": trend_data_e,
            "camera_top10": camera_distribution,
            "hour_distribution": hour_distribution,
        }
    })
