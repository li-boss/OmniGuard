import io
import threading
import time
import wave

import numpy as np
from flask import Blueprint, current_app, jsonify, request

from models import AlarmEvent, db
from services.active_liveness import active_liveness_challenges
from services.multimodal_fusion import audio_detection_service, fusion_engine
from services.ws_handler import push_alarm


multimodal_bp = Blueprint("multimodal_api", __name__)
_last_alarm_at = {}
_alarm_lock = threading.Lock()


def ok(data, status=200):
    return jsonify({"code": 0, "message": "ok", "data": data}), status


def bad_request(message):
    return jsonify({"code": 400, "message": message, "data": None}), 400


def _evaluate(payload):
    camera_id = str(payload.get("camera_id") or payload.get("cameraId") or "cam-1")
    object_id = payload.get("object_id") or payload.get("objectId")
    zone_id = payload.get("zone_id") or payload.get("zoneId")
    in_zone = bool(payload.get("in_zone", payload.get("inZone", zone_id is not None)))
    decision = fusion_engine.evaluate(camera_id, object_id, in_zone=in_zone)

    event_id = None
    alarm_suppressed = False
    if decision.triggered and payload.get("create_alarm", payload.get("createAlarm", True)):
        cooldown = float(current_app.config.get("AUDIO_ALARM_COOLDOWN_SECONDS", 30))
        now = time.time()
        with _alarm_lock:
            last_alarm = _last_alarm_at.get(camera_id, 0.0)
            if now - last_alarm < cooldown:
                alarm_suppressed = True
            else:
                _last_alarm_at[camera_id] = now
        if not alarm_suppressed:
            event = AlarmEvent(
                alarm_type="multimodal_anomaly",
                level=decision.severity,
                camera_id=camera_id,
                zone_id=zone_id,
                description="检测到异常声音或多模态联动风险",
                detection_data=decision.to_dict(),
                status="pending",
            )
            db.session.add(event)
            db.session.commit()
            event_id = event.id
            push_alarm(event.to_dict())
    result = decision.to_dict()
    result["alarm_id"] = event_id
    result["alarm_suppressed"] = alarm_suppressed
    return result


@multimodal_bp.post("/audio-events")
def add_audio_event():
    payload = request.get_json(silent=True) or {}
    if not payload.get("label"):
        return bad_request("label is required")
    try:
        fusion_engine.add_audio_event(
            payload.get("camera_id") or payload.get("cameraId") or "cam-1",
            payload["label"],
            payload.get("confidence", 1.0),
            payload.get("timestamp"),
        )
        return ok(_evaluate(payload), 201)
    except (TypeError, ValueError) as exc:
        return bad_request(str(exc))


@multimodal_bp.post("/emotion-events")
def add_emotion_event():
    payload = request.get_json(silent=True) or {}
    if not payload.get("emotion") or payload.get("object_id", payload.get("objectId")) is None:
        return bad_request("emotion and object_id are required")
    try:
        fusion_engine.add_emotion_event(
            payload.get("camera_id") or payload.get("cameraId") or "cam-1",
            payload.get("object_id", payload.get("objectId")),
            payload["emotion"],
            payload.get("confidence", 1.0),
            payload.get("timestamp"),
        )
        return ok(_evaluate(payload), 201)
    except (TypeError, ValueError) as exc:
        return bad_request(str(exc))


@multimodal_bp.post("/evaluate")
def evaluate_fusion():
    return ok(_evaluate(request.get_json(silent=True) or {}))


@multimodal_bp.post("/analyze-wav")
def analyze_wav():
    upload = request.files.get("audio")
    if not upload:
        return bad_request("a PCM WAV file is required in the audio field")
    try:
        raw_audio = upload.read()
        max_bytes = int(current_app.config.get("AUDIO_UPLOAD_MAX_BYTES", 5 * 1024 * 1024))
        if len(raw_audio) > max_bytes:
            return bad_request(f"audio chunk exceeds {max_bytes} bytes")
        with wave.open(io.BytesIO(raw_audio), "rb") as wav:
            if wav.getnchannels() not in (1, 2) or wav.getsampwidth() != 2:
                return bad_request("only 16-bit mono/stereo PCM WAV is supported")
            sample_rate = wav.getframerate()
            channels = wav.getnchannels()
            samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
            if channels == 2:
                samples = samples.reshape(-1, 2).mean(axis=1)
        events = audio_detection_service.analyze(samples, sample_rate)
        camera_id = request.form.get("camera_id", "cam-1")
        for event in events:
            fusion_engine.add_audio_event(camera_id, event["label"], event["score"])
        create_alarm = request.form.get("create_alarm", "true").lower() in {"1", "true", "yes"}
        rms = float(np.sqrt(np.mean(np.square(samples)))) if samples.size else 0.0
        result = {
            "events": events,
            "sample_rate": sample_rate,
            "duration_seconds": round(samples.size / float(sample_rate), 3),
            "rms": round(rms, 5),
            "detectors": audio_detection_service.status(),
        }
        result.update(_evaluate({"camera_id": camera_id, "create_alarm": create_alarm}))
        return ok(result)
    except (ValueError, wave.Error) as exc:
        return bad_request(str(exc))


@multimodal_bp.get("/audio-status")
def audio_status():
    camera_monitor = current_app.config.get("audio_monitor")
    return ok({
        "ready": True,
        "chunk_seconds": current_app.config.get("AUDIO_CHUNK_SECONDS", 0.5),
        "alarm_cooldown_seconds": current_app.config.get("AUDIO_ALARM_COOLDOWN_SECONDS", 30),
        "detectors": audio_detection_service.status(),
        "camera_audio_monitor": camera_monitor.status() if camera_monitor else {
            "enabled": False,
            "running": False,
            "cameras": {},
        },
    })


@multimodal_bp.post("/liveness/challenges")
def create_liveness_challenge():
    payload = request.get_json(silent=True) or {}
    subject_id = payload.get("subject_id") or payload.get("subjectId")
    if subject_id is None:
        return bad_request("subject_id is required")
    return ok(active_liveness_challenges.create(subject_id, payload.get("length", 3)), 201)


@multimodal_bp.post("/liveness/challenges/<challenge_id>/observations")
def observe_liveness_challenge(challenge_id):
    payload = request.get_json(silent=True) or {}
    if payload.get("action") not in ("turn_left", "turn_right", "blink", "open_mouth"):
        return bad_request("invalid action")
    try:
        return ok(active_liveness_challenges.observe(challenge_id, payload["action"], payload.get("confidence", 1.0)))
    except KeyError as exc:
        return jsonify({"code": 404, "message": str(exc), "data": None}), 404


@multimodal_bp.get("/liveness/challenges/<challenge_id>")
def get_liveness_challenge(challenge_id):
    try:
        return ok(active_liveness_challenges.get(challenge_id))
    except KeyError as exc:
        return jsonify({"code": 404, "message": str(exc), "data": None}), 404
