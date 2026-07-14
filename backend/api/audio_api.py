from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import jwt_required

from services.audio_event_detector import get_audio_event_detector


audio_bp = Blueprint("audio_api", __name__)


def _success(data=None, message="ok"):
    return jsonify({"code": 0, "message": message, "data": data or {}})


def _error(message, status=400):
    return jsonify({"code": 1, "message": message, "data": None}), status


@audio_bp.get("/status")
@jwt_required()
def audio_status():
    response = _success(get_audio_event_detector(current_app).status())
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@audio_bp.get("/devices")
@jwt_required()
def audio_devices():
    try:
        return _success({"items": get_audio_event_detector(current_app).list_devices()})
    except RuntimeError as exc:
        return _error(str(exc), 503)


@audio_bp.post("/start")
@jwt_required()
def start_audio_detection():
    payload = request.get_json(silent=True) or {}
    device = payload.get("device")
    if isinstance(device, str) and device.isdigit():
        device = int(device)
    try:
        status = get_audio_event_detector(current_app).start(device=device)
        return _success(status, "声音检测已启动")
    except RuntimeError as exc:
        return _error(str(exc), 503)
    except Exception as exc:
        current_app.logger.exception("Failed to start audio detection")
        return _error(f"声音检测启动失败：{exc}", 500)


@audio_bp.post("/stop")
@jwt_required()
def stop_audio_detection():
    try:
        status = get_audio_event_detector(current_app).stop()
        return _success(status, "声音检测已停止，麦克风已释放")
    except Exception as exc:
        current_app.logger.exception("Failed to stop audio detection")
        return _error(f"声音检测停止失败：{exc}", 500)
