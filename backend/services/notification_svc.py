import logging
import requests
from datetime import datetime

from backend.app import db
from backend.models.alarm import AlarmEvent

logger = logging.getLogger(__name__)

DINGTALK_WEBHOOK_URL = ''
ESCALATION_RECIPIENTS = {
    0: '',
    1: '',
    2: '',
}

SEVERITY_ESCALATION_MAP = {
    'low': 0,
    'medium': 1,
    'high': 2,
    'critical': 2,
}


class NotificationService:

    def push_dingtalk(self, alarm, escalation_level=None):
        if not DINGTALK_WEBHOOK_URL:
            logger.warning('DingTalk webhook URL not configured, skipping notification')
            return False

        level = escalation_level if escalation_level is not None else alarm.escalation_level
        severity_emoji = {'low': '🟢', 'medium': '🟡', 'high': '🔴', 'critical': '🚨'}
        emoji = severity_emoji.get(alarm.severity, '⚠️')

        title = f'{emoji} 安防告警 - {alarm.type}'
        text = (
            f'**告警类型**: {alarm.type}\n\n'
            f'**严重级别**: {alarm.severity}\n\n'
            f'**摄像头**: {alarm.camera_id}\n\n'
            f'**告警时间**: {alarm.created_at.strftime("%Y-%m-%d %H:%M:%S") if alarm.created_at else "N/A"}\n\n'
            f'**上报级别**: Level {level}\n\n'
            f'**描述**: {alarm.description or "无"}\n\n'
        )
        if alarm.snapshot_url:
            text += f'**截图**: [查看]({alarm.snapshot_url})\n\n'

        payload = {
            'msgtype': 'markdown',
            'markdown': {
                'title': title,
                'text': text,
            },
            'at': {
                'atMobiles': [],
                'isAtAll': level >= 2,
            },
        }

        try:
            resp = requests.post(
                DINGTALK_WEBHOOK_URL,
                json=payload,
                timeout=10,
            )
            if resp.status_code == 200:
                result = resp.json()
                if result.get('errcode') == 0:
                    alarm.dingtalk_notified = True
                    db.session.commit()
                    logger.info('DingTalk notification sent for alarm %s', alarm.id)
                    return True
                else:
                    logger.error('DingTalk API error: %s', result)
            else:
                logger.error('DingTalk HTTP error: %s', resp.status_code)
        except Exception as e:
            logger.error('DingTalk notification failed: %s', str(e))

        return False

    def check_escalation(self, alarm_id=None):
        if alarm_id:
            alarm = AlarmEvent.query.get(alarm_id)
            if alarm and alarm.should_escalate():
                return self._escalate_alarm(alarm)
            return False

        pending_alarms = AlarmEvent.query.filter(
            AlarmEvent.status.in_(['pending', 'handling']),
            AlarmEvent.escalation_deadline != None,
        ).all()

        escalated = []
        for alarm in pending_alarms:
            if alarm.should_escalate():
                if self._escalate_alarm(alarm):
                    escalated.append(alarm.id)
        return escalated

    def _escalate_alarm(self, alarm):
        if alarm.escalate():
            db.session.commit()
            self.push_dingtalk(alarm, escalation_level=alarm.escalation_level)
            from backend.services.ws_handler import push_alarm
            push_alarm(alarm.to_dict())
            logger.info('Alarm %s escalated to level %d', alarm.id, alarm.escalation_level)
            return True
        return False


notification_svc = NotificationService()


def push_dingtalk(alarm, escalation_level=None):
    return notification_svc.push_dingtalk(alarm, escalation_level=escalation_level)


def check_escalation(alarm_id=None):
    return notification_svc.check_escalation(alarm_id=alarm_id)
