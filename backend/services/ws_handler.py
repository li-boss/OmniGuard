from datetime import datetime

from flask import request
from flask_socketio import emit

from extensions import socketio

# 摄像头订阅关系
camera_subscribe = {}


def now_ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@socketio.on("subscribe")
def handle_subscribe(data):
    sid = request.sid
    camera_ids = data.get("camera_ids", [])

    for cid in camera_ids:
        if cid not in camera_subscribe:
            camera_subscribe[cid] = []

        if sid not in camera_subscribe[cid]:
            camera_subscribe[cid].append(sid)

    emit(
        "subscribe_success",
        {
            "msg": "订阅成功",
            "camera_ids": camera_ids
        }
    )


@socketio.on("ack")
def handle_ack(data):
    alarm_id = data.get("alarm_id")
    print(f"客户端确认告警：{alarm_id}")


@socketio.on("heartbeat")
def handle_heartbeat():
    emit(
        "heartbeat",
        {
            "ts": now_ts()
        }
    )


def push_alarm(alarm_data):
    """
    推送告警
    """

    cid = alarm_data.get("camera_id")

    target_sids = camera_subscribe.get(cid, [])

    alarm_msg = {
        "id": alarm_data["id"],
        "camera_id": cid,
        "type": alarm_data["alarm_type"],
        "severity": alarm_data["severity"],
        "content": alarm_data["content"],
        "time": now_ts()
    }

    for sid in target_sids:
        socketio.emit(
            "alarm",
            alarm_msg,
            to=sid
        )

    # 推送钉钉
    from services.notification_svc import push_dingtalk

    push_dingtalk(
        alarm_data,
        escalation_level=alarm_data["severity"]
    )