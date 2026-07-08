import logging
from flask import request
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

socketio = SocketIO(cors_allowed_origins="*", async_mode='threading')

_subscribed_cameras = {}


@socketio.on('connect')
def on_connect():
    logger.info('Client connected: %s', request.sid)


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    if sid in _subscribed_cameras:
        del _subscribed_cameras[sid]
    logger.info('Client disconnected: %s', sid)


@socketio.on('subscribe')
def on_subscribe(data):
    sid = request.sid
    camera_ids = data.get('camera_ids', [])
    _subscribed_cameras[sid] = set(camera_ids)
    logger.info('Client %s subscribed to cameras: %s', sid, camera_ids)


@socketio.on('ack')
def on_ack(data):
    alarm_id = data.get('alarm_id')
    logger.info('Alarm %s acknowledged by client', alarm_id)


def push_alarm(alarm_dict):
    camera_id = alarm_dict.get('camera_id')
    for sid, cameras in _subscribed_cameras.items():
        if not cameras or camera_id in cameras:
            socketio.emit('alarm', alarm_dict, room=sid)
    logger.info('Pushed alarm %s to subscribers', alarm_dict.get('id'))


def push_heartbeat():
    from datetime import datetime
    socketio.emit('heartbeat', {'ts': datetime.utcnow().isoformat()})
