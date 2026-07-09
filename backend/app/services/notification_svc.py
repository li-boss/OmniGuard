import logging

import requests
from flask import current_app

from ..extensions import db
from ..models import AlarmEvent


logger = logging.getLogger(__name__)


SEVERITY_ESCALATION_MAP = {
    "low": 0,
    "medium": 1,
    "high": 2,
    "critical": 2,
}


class NotificationService:
    def push_dingtalk(self, alarm, escalation_level=None):
        webhook = current_app.config.get("DINGTALK_WEBHOOK")
        if not webhook:
            return {"sent": False, "reason": "DINGTALK_WEBHOOK is empty"}

        level = escalation_level if escalation_level is not None else alarm.escalation_level
        title = f"Security alarm - {alarm.event_type}"
        text = (
            f"### {title}\n"
            f"- Severity: {alarm.severity}\n"
            f"- Camera: {alarm.camera_id}\n"
            f"- Status: {alarm.status}\n"
            f"- Escalation level: {level}\n"
            f"- Time: {alarm.occurred_at.isoformat() if alarm.occurred_at else 'N/A'}\n"
            f"- Description: {alarm.description or 'N/A'}\n"
        )
        if alarm.snapshot_url:
            text += f"- Snapshot: {alarm.snapshot_url}\n"

        try:
            response = requests.post(
                webhook,
                json={"msgtype": "markdown", "markdown": {"title": title, "text": text}},
                timeout=10,
            )
        except requests.RequestException as exc:
            logger.warning("DingTalk notification failed for alarm %s: %s", alarm.id, exc)
            return {"sent": False, "reason": str(exc)}

        sent = response.ok
        if sent:
            alarm.dingtalk_notified = True
            db.session.commit()
        return {"sent": sent, "statusCode": response.status_code}

    def check_escalation(self, alarm_id=None):
        if alarm_id is not None:
            alarm = db.session.get(AlarmEvent, alarm_id)
            if alarm and alarm.should_escalate():
                return self._escalate_alarm(alarm)
            return False

        pending_alarms = AlarmEvent.query.filter(
            AlarmEvent.status.in_(["pending", "handling"]),
            AlarmEvent.escalation_deadline.isnot(None),
        ).all()
        escalated = []
        for alarm in pending_alarms:
            if alarm.should_escalate() and self._escalate_alarm(alarm):
                escalated.append(alarm.id)
        return escalated

    def _escalate_alarm(self, alarm):
        if not alarm.escalate():
            return False
        db.session.commit()
        self.push_dingtalk(alarm, escalation_level=alarm.escalation_level)
        from .ws_handler import push_alarm

        push_alarm(alarm.to_dict())
        return True


notification_svc = NotificationService()


def push_dingtalk(alarm, escalation_level=None):
    return notification_svc.push_dingtalk(alarm, escalation_level=escalation_level)


def check_escalation(alarm_id=None):
    return notification_svc.check_escalation(alarm_id=alarm_id)
