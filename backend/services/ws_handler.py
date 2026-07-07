from app import socketio


def emit_alarm(alarm):
    socketio.emit("alarm:new", alarm, namespace="/")
