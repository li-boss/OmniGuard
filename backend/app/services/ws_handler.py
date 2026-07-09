from datetime import datetime, timezone
import logging

from flask import request

from ..extensions import socketio


logger = logging.getLogger(__name__)
_subscribed_cameras = {}


def init_socket_events(socketio_instance):
    @socketio_instance.on("connect")
    def connect():
        logger.info("Socket connected: %s", request.sid)
        socketio_instance.emit("heartbeat", {
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    @socketio_instance.on("disconnect")
    def disconnect():
        _subscribed_cameras.pop(request.sid, None)
        logger.info("Socket disconnected: %s", request.sid)

    @socketio_instance.on("subscribe")
    def subscribe(payload):
        camera_ids = (payload or {}).get("camera_ids") or (payload or {}).get("cameraIds") or []
        _subscribed_cameras[request.sid] = {str(camera_id) for camera_id in camera_ids}
        socketio_instance.emit("subscribed", {
            "cameraIds": camera_ids,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    @socketio_instance.on("ack")
    def ack(payload):
        logger.info("Alarm ack from %s: %s", request.sid, payload or {})
        socketio_instance.emit("ack_received", payload or {})


def push_alarm(alarm_payload):
    camera_id = str(alarm_payload.get("cameraId") or alarm_payload.get("camera_id") or "")
    delivered = False
    for sid, cameras in list(_subscribed_cameras.items()):
        if not cameras or camera_id in cameras:
            socketio.emit("alarm", alarm_payload, room=sid)
            delivered = True
    if not delivered:
        socketio.emit("alarm", alarm_payload, namespace="/")


def push_heartbeat():
    socketio.emit("heartbeat", {"ts": datetime.now(timezone.utc).isoformat()})
