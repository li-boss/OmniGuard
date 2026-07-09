from collections import Counter
from datetime import datetime, timezone

from ..models import AlarmEvent


def generate_daily_report():
    alarms = AlarmEvent.query.all()
    severity = Counter(alarm.severity for alarm in alarms)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "alarmCount": len(alarms),
        "severity": dict(severity),
        "summary": "今日系统运行正常，请重点关注未处置高等级告警。",
    }
