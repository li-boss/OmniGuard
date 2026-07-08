from datetime import datetime, timezone

from app import socketio


def init_socket_events(socketio_instance):
    @socketio_instance.on("connect")
    def connect(auth=None):
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


def emit_alarm(alarm):
    # Emit on both channels to satisfy B's frontend ("alarm") and other parts ("alarm:new")
    socketio.emit("alarm:new", alarm, namespace="/")
    socketio.emit("alarm", alarm, namespace="/")
