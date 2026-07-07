import json
from datetime import date, datetime, time, timedelta

from sqlalchemy import func

from extensions import db
from models.alarm import AlarmEvent
from services.notification_svc import push_dingtalk


def generate_daily_report():
    """
    生成昨日告警统计日报
    """

    yesterday = date.today() - timedelta(days=1)

    start_time = datetime.combine(
        yesterday,
        time.min
    )

    end_time = datetime.combine(
        yesterday,
        time.max
    )

    total = AlarmEvent.query.filter(
        AlarmEvent.create_time.between(
            start_time,
            end_time
        )
    ).count()

    handled = AlarmEvent.query.filter(
        AlarmEvent.create_time.between(
            start_time,
            end_time
        ),
        AlarmEvent.handle_status == "handled"
    ).count()

    level_result = (
        db.session.query(
            AlarmEvent.severity,
            func.count(AlarmEvent.id)
        )
        .filter(
            AlarmEvent.create_time.between(
                start_time,
                end_time
            )
        )
        .group_by(
            AlarmEvent.severity
        )
        .all()
    )

    report = {
        "date": str(yesterday),
        "total_alarm": total,
        "handled_count": handled,
        "handle_rate": round(
            handled / total * 100,
            2
        ) if total else 0,
        "level_dist": {
            k: v
            for k, v in level_result
        }
    }

    push_dingtalk(
        {
            "camera_id": "system",
            "alarm_type": "日报",
            "content": json.dumps(
                report,
                ensure_ascii=False,
                indent=2
            )
        },
        escalation_level="low"
    )

    return report