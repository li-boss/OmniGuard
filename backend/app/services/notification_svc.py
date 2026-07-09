import requests
from flask import current_app

from ..extensions import db
from ..models import AlarmEvent


def push_dingtalk(alarm, escalation_level=1):
    webhook = current_app.config.get("DINGTALK_WEBHOOK")
    if not webhook:
        return {"sent": False, "reason": "DINGTALK_WEBHOOK is empty"}

    content = f"告警{alarm.id}: {alarm.title} / {alarm.severity} / level {escalation_level}"
    response = requests.post(
        webhook,
        json={"msgtype": "text", "text": {"content": content}},
        timeout=5,
    )
    return {"sent": response.ok, "statusCode": response.status_code}


def check_escalation(alarm_id):
    alarm = db.session.get(AlarmEvent, alarm_id)
    if not alarm or alarm.status != "pending":
        return {"sent": False, "reason": "alarm not pending"}
    if alarm.severity in {"high", "critical"}:
        return push_dingtalk(alarm, escalation_level=1)
    return {"sent": False, "reason": "severity does not require escalation"}
