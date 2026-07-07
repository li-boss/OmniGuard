from datetime import datetime, timedelta

from flask import Blueprint, jsonify

from models import AlarmEvent

dashboard_bp = Blueprint("dashboard_api", __name__)


@dashboard_bp.get("/summary")
def summary():
    total = AlarmEvent.query.count()
    pending = AlarmEvent.query.filter_by(status="pending").count()
    return jsonify({"total_alarms": total, "pending_alarms": pending})


@dashboard_bp.get("/alarm-trend")
def alarm_trend():
    today = datetime.utcnow().date()
    data = []
    for offset in range(6, -1, -1):
        day = today - timedelta(days=offset)
        count = AlarmEvent.query.filter(
            AlarmEvent.created_at >= datetime.combine(day, datetime.min.time()),
            AlarmEvent.created_at <= datetime.combine(day, datetime.max.time()),
        ).count()
        data.append({"date": day.isoformat(), "count": count})
    return jsonify(data)


@dashboard_bp.get("/disposal-rate")
def disposal_rate():
    total = AlarmEvent.query.count()
    handled = AlarmEvent.query.filter(AlarmEvent.status.in_(["handled", "ignored"])).count()
    return jsonify({"rate": handled / total if total else 0})
