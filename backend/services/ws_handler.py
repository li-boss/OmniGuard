import logging
from datetime import datetime, timezone
from flask import request
from flask_socketio import SocketIO

logger = logging.getLogger(__name__)

socketio = SocketIO(cors_allowed_origins="*", transports=["polling"])

_subscribed_cameras = {}


def init_socket_events(socketio_instance):
    @socketio_instance.on("connect")
    def connect(auth=None):
        logger.info('Client connected: %s', request.sid)
        socketio_instance.emit("heartbeat", {
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    @socketio_instance.on("disconnect")
    def disconnect():
        sid = request.sid
        if sid in _subscribed_cameras:
            del _subscribed_cameras[sid]
        logger.info('Client disconnected: %s', sid)

    @socketio_instance.on("subscribe")
    def subscribe(payload):
        sid = request.sid
        camera_ids = (payload or {}).get("camera_ids") or (payload or {}).get("cameraIds") or []
        _subscribed_cameras[sid] = set(camera_ids)
        
        socketio_instance.emit("subscribed", {
            "cameraIds": camera_ids,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        logger.info('Client %s subscribed to cameras: %s', sid, camera_ids)

    @socketio_instance.on("ack")
    def ack(payload):
        data = payload or {}
        alarm_id = data.get('alarm_id') or data.get('alarmId')
        logger.info('Alarm %s acknowledged by client', alarm_id)
        socketio_instance.emit("ack_received", data)


def push_alarm(alarm_dict):
    """向匹配了摄像头订阅的客户端（或者所有）推送。"""
    camera_id = alarm_dict.get('camera_id') or alarm_dict.get('cameraId')
    
    # 1. 拷贝以双向扩展字段名称以实现兼容
    full_dict = dict(alarm_dict)
    
    # 映射摄像头字段
    if 'camera_id' in full_dict and 'cameraId' not in full_dict:
        full_dict['cameraId'] = full_dict['camera_id']
    if 'cameraId' in full_dict and 'camera_id' not in full_dict:
        full_dict['camera_id'] = full_dict['cameraId']
        
    # 映射类型字段
    if 'type' in full_dict and 'alarm_type' not in full_dict:
        full_dict['alarm_type'] = full_dict['type']
        full_dict['eventType'] = full_dict['type']
    if 'alarm_type' in full_dict and 'type' not in full_dict:
        full_dict['type'] = full_dict['alarm_type']
        full_dict['eventType'] = full_dict['alarm_type']
        
    type_map = {
        "electronic_fence": "围栏入侵告警",
        "fall": "异常活动 - 跌倒",
        "fire": "异常活动 - 火情"
    }
    raw_type = full_dict.get('alarm_type')
    if raw_type in type_map:
        friendly_type = type_map[raw_type]
        full_dict['alarm_type'] = friendly_type
        full_dict['type'] = friendly_type
        full_dict['eventType'] = friendly_type
        
    # 映射严重程度字段
    if 'severity' in full_dict and 'level' not in full_dict:
        full_dict['level'] = full_dict['severity']
    if 'level' in full_dict and 'severity' not in full_dict:
        full_dict['severity'] = full_dict['level']
        
    # 映射截图字段
    if 'snapshot_url' in full_dict and 'snapshot_path' not in full_dict:
        full_dict['snapshot_path'] = full_dict['snapshot_url']
        full_dict['snapshotUrl'] = full_dict['snapshot_url']
    if 'snapshot_path' in full_dict and 'snapshot_url' not in full_dict:
        full_dict['snapshot_url'] = full_dict['snapshot_path']
        full_dict['snapshotUrl'] = full_dict['snapshot_path']
        
    # 映射发生时间字段
    if 'created_at' in full_dict and 'occurredAt' not in full_dict:
        full_dict['occurredAt'] = full_dict['created_at']
    if 'occurredAt' in full_dict and 'created_at' not in full_dict:
        full_dict['created_at'] = full_dict['occurredAt']
        
    # 映射处置时间字段
    if 'handle_time' in full_dict and 'handledAt' not in full_dict:
        full_dict['handledAt'] = full_dict['handle_time']
    if 'handledAt' in full_dict and 'handle_time' not in full_dict:
        full_dict['handle_time'] = full_dict['handledAt']

    # 默认标题和描述（如果不存在）
    if 'title' not in full_dict:
        base_type = full_dict.get('alarm_type', '围栏入侵告警')
        full_dict['title'] = f"{base_type} - 摄像头 {camera_id}"
    if 'description' not in full_dict:
        full_dict['description'] = f"目标触发 {full_dict.get('type')} 规则"

    # 按订阅推送
    has_subscribers = False
    for sid, cameras in _subscribed_cameras.items():
        if not cameras or camera_id in cameras:
            has_subscribers = True
            socketio.emit('alarm', full_dict, room=sid)
    
    # 如果没有订阅者，才全局广播
    if not has_subscribers:
        socketio.emit('alarm', full_dict)
    
    logger.info('Pushed alarm %s to subscribers', full_dict.get('id'))


def emit_alarm(alarm):
    """支持模型对象和字典结构的触发函数。"""
    if hasattr(alarm, "to_dict"):
        push_alarm(alarm.to_dict())
    elif isinstance(alarm, dict):
        push_alarm(alarm)
    else:
        push_alarm(vars(alarm))


def push_heartbeat():
    socketio.emit('heartbeat', {
        'ts': datetime.now(timezone.utc).isoformat()
    })
