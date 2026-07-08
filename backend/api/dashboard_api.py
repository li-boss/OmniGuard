from datetime import datetime, timedelta

from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from backend.app import db
from backend.models.alarm import AlarmEvent

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')


@dashboard_bp.route('/summary', methods=['GET'])
@jwt_required()
def get_summary():
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    total_alarms = AlarmEvent.query.count()
    pending_alarms = AlarmEvent.query.filter(AlarmEvent.status == 'pending').count()
    handling_alarms = AlarmEvent.query.filter(AlarmEvent.status == 'handling').count()
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

    severity_stats = db.session.query(
        AlarmEvent.severity, func.count(AlarmEvent.id)
    ).group_by(AlarmEvent.severity).all()
    severity_distribution = {s: c for s, c in severity_stats}

    type_stats = db.session.query(
        AlarmEvent.type, func.count(AlarmEvent.id)
    ).group_by(AlarmEvent.type).all()
    type_distribution = {t: c for t, c in type_stats}

    trend_data = []
    for i in range(6, -1, -1):
        day = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        count = AlarmEvent.query.filter(
            AlarmEvent.created_at >= day_start,
            AlarmEvent.created_at < day_end,
        ).count()
        trend_data.append({
            'date': day_start.strftime('%Y-%m-%d'),
            'count': count,
        })

    camera_stats = db.session.query(
        AlarmEvent.camera_id, func.count(AlarmEvent.id)
    ).group_by(AlarmEvent.camera_id).order_by(func.count(AlarmEvent.id).desc()).limit(10).all()
    camera_distribution = [{'camera_id': c, 'count': cnt} for c, cnt in camera_stats]

    hour_distribution = []
    for h in range(24):
        count = AlarmEvent.query.filter(
            func.extract('hour', AlarmEvent.created_at) == h
        ).count()
        hour_distribution.append({'hour': h, 'count': count})

    return jsonify({
        'total_alarms': total_alarms,
        'pending_alarms': pending_alarms,
        'handling_alarms': handling_alarms,
        'resolved_today': resolved_today,
        'today_alarms': today_alarms,
        'week_alarms': week_alarms,
        'severity_distribution': severity_distribution,
        'type_distribution': type_distribution,
        'trend_7days': trend_data,
        'camera_top10': camera_distribution,
        'hour_distribution': hour_distribution,
    })
