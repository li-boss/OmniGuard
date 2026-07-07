from datetime import date, datetime, time

from flask import jsonify
from sqlalchemy import func

from api import dashboard_bp
from extensions import db
from models.alarm import AlarmEvent



@dashboard_bp.route(
    "/summary",
    methods=["GET"]
)
def dashboard_summary():

    today_start = datetime.combine(
        date.today(),
        time.min
    )


    today_total = AlarmEvent.query.filter(
        AlarmEvent.create_time >= today_start
    ).count()


    pending_count = AlarmEvent.query.filter_by(
        handle_status="pending"
    ).count()


    level_result = (
        db.session.query(
            AlarmEvent.severity,
            func.count(AlarmEvent.id)
        )
        .group_by(
            AlarmEvent.severity
        )
        .all()
    )


    level_dist = {
        key: value
        for key, value in level_result
    }


    return jsonify({
        "code": 200,
        "data": {
            "today_total": today_total,
            "pending_count": pending_count,
            "level_dist": level_dist
        }
    })