from datetime import datetime, timezone

from ..extensions import socketio


def init_socket_events(socketio_instance):
    @socketio_instance.on("connect")
    def connect():
        socketio_instance.emit("heartbeat", {
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    @socketio_instance.on("subscribe")
    def subscribe(payload):
        socketio_instance.emit("subscribed", {
            "cameraIds": (payload or {}).get("camera_ids", []),
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    @socketio_instance.on("ack")
    def ack(payload):
        socketio_instance.emit("ack_received", payload or {})


def push_alarm(alarm_payload):
    socketio.emit("alarm", alarm_payload, namespace="/")
