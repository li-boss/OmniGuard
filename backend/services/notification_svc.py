from datetime import datetime

import requests

from config import DINGTALK_WEBHOOK
from extensions import db
from models.alarm import AlarmEvent


LEVEL_MAP = {
    "low": {
        "title": "普通告警",
        "at_all": False
    },
    "mid": {
        "title": "重要告警",
        "at_all": False
    },
    "high": {
        "title": "紧急告警",
        "at_all": True
    }
}


def push_dingtalk(alarm, escalation_level="low"):
    """
    推送钉钉消息
    """

    level_info = LEVEL_MAP.get(
        escalation_level,
        LEVEL_MAP["low"]
    )

    msg = {
        "msgtype": "text",
        "text": {
            "content": f"""【智慧校园安防-{level_info['title']}】

告警ID：{alarm.get('id', '-')}

摄像头：{alarm.get('camera_id', '-')}

类型：{alarm.get('alarm_type', '-')}

时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

描述：{alarm.get('content', '')}
"""
        },
        "at": {
            "isAtAll": level_info["at_all"]
        }
    }

    try:
        response = requests.post(
            DINGTALK_WEBHOOK,
            json=msg,
            timeout=5
        )

        return response.json()

    except Exception as e:
        print("钉钉发送失败：", e)
        return None


def check_escalation(alarm_id):
    """
    超时升级
    """

    alarm = db.session.get(
        AlarmEvent,
        alarm_id
    )

    if alarm is None:
        return False

    delta = datetime.now() - alarm.create_time

    if (
        delta.total_seconds() > 300
        and alarm.handle_status == "pending"
    ):

        alarm.severity = "high"

        db.session.commit()

        push_dingtalk(
            alarm.to_dict(),
            escalation_level="high"
        )

        return True

    return False