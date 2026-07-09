from datetime import datetime
import html
import os
from pathlib import Path
import time

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from ..core_cv.face_recognizer import FaceRecognizer, SFACE_FEATURE_DIM
from ..core_cv.fall_detector import FallDetector
from ..extensions import db
from ..models import FaceRecord


stream_bp = Blueprint("streams", __name__)
_face_recognizer = FaceRecognizer()
_fall_detector = FallDetector(confirm_frames=int(os.getenv("FALL_CONFIRM_FRAMES", "2")))
_face_cache = {"loaded_at": 0.0, "items": []}
_fall_alarm_state = {"last_alarm_at": 0.0}


try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - exercised only when optional runtime dep is absent
    cv2 = None
    np = None

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover - optional text rendering dependency
    Image = None
    ImageDraw = None
    ImageFont = None


_FONT_CACHE = {}


def _svg_response(title, message, status=200):
    safe_title = html.escape(title)
    safe_message = html.escape(message)
    safe_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
      <rect width="960" height="540" fill="#111820"/>
      <rect x="34" y="34" width="892" height="472" fill="none" stroke="#3b5163" stroke-width="3"/>
      <text x="64" y="150" fill="#edf5f7" font-family="Arial, sans-serif" font-size="42" font-weight="700">{safe_title}</text>
      <text x="64" y="214" fill="#a7bac8" font-family="Arial, sans-serif" font-size="24">{safe_message}</text>
      <text x="64" y="276" fill="#68d19d" font-family="Arial, sans-serif" font-size="24">{safe_time}</text>
      <circle cx="820" cy="138" r="12" fill="#d94841"/>
      <text x="842" y="147" fill="#f8d8d6" font-family="Arial, sans-serif" font-size="22">OFFLINE</text>
    </svg>
    """
    return Response(svg.strip(), status=status, mimetype="image/svg+xml")


def _resolve_source():
    source = (
        request.args.get("src")
        or request.args.get("source")
        or current_app.config.get("VIDEO_SOURCE_URL")
        or os.getenv("VIDEO_SOURCE_URL")
        or os.getenv("CAMERA_SOURCE_URL")
        or current_app.config.get("RTMP_BASE_URL")
        or "0"
    )
    source = str(source).strip()
    if source.isdigit():
        return int(source)
    return source


def _open_capture(source):
    capture = cv2.VideoCapture(source)
    try:
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    except Exception:
        pass
    return capture


def _contains_non_ascii(text):
    return any(ord(char) > 127 for char in str(text))


def _font_path():
    candidates = [
        Path("C:/Windows/Fonts/NotoSansSC-VF.ttf"),
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("C:/Windows/Fonts/Deng.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _load_font(size):
    if ImageFont is None:
        return None
    if size in _FONT_CACHE:
        return _FONT_CACHE[size]

    path = _font_path()
    if path is None:
        return None
    font = ImageFont.truetype(str(path), size=size)
    _FONT_CACHE[size] = font
    return font


def _text_size(text, font_size=24):
    text = str(text)
    if ImageDraw is not None and _contains_non_ascii(text):
        font = _load_font(font_size)
        if font is not None:
            canvas = Image.new("RGB", (1, 1))
            draw = ImageDraw.Draw(canvas)
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            return right - left, bottom - top

    scale = font_size / 34.0
    (width, height), _baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 2)
    return width, height


def _draw_text(frame, text, position, font_size=24, color=(255, 255, 255)):
    text = str(text)
    x, y = position
    if Image is not None and ImageDraw is not None and np is not None and _contains_non_ascii(text):
        font = _load_font(font_size)
        if font is not None:
            image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            draw = ImageDraw.Draw(image)
            draw.text((x, y), text, font=font, fill=(color[2], color[1], color[0]))
            frame[:] = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
            return

    scale = font_size / 34.0
    cv2.putText(frame, text, (x, y + font_size), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)


def _draw_box_label(frame, box, label, color, font_size=24):
    x1, y1, x2, y2 = [int(round(value)) for value in box]
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(frame.shape[1] - 1, x2)
    y2 = min(frame.shape[0] - 1, y2)
    if x2 <= x1 or y2 <= y1:
        return

    text_width, text_height = _text_size(label, font_size=font_size)
    label_height = max(34, text_height + 14)
    label_width = max(x2 - x1, text_width + 18, 150)
    label_top = max(0, y1 - label_height)
    text_top = label_top + max(4, (label_height - text_height) // 2 - 1)

    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
    cv2.rectangle(frame, (x1, label_top), (min(frame.shape[1] - 1, x1 + label_width), y1), color, -1)
    _draw_text(frame, label, (x1 + 8, text_top), font_size=font_size, color=(18, 24, 32))


def _known_faces():
    now = time.time()
    if now - _face_cache["loaded_at"] < 3:
        return _face_cache["items"]

    items = []
    changed = False
    records = FaceRecord.query.order_by(FaceRecord.id.asc()).all()
    for record in records:
        features = record.get_features()
        if (not features or any(len(feature) != SFACE_FEATURE_DIM for feature in features)) and record.image_preview:
            features = _face_recognizer.extract_features(record.image_preview, allow_fallback=False)
            if features:
                record.set_features(features)
                changed = True
        if features:
            items.append({
                "id": record.id,
                "studentId": record.student_id,
                "name": record.name,
                "feature": features[0],
                "features": features,
            })
    if changed:
        db.session.commit()

    _face_cache["loaded_at"] = now
    _face_cache["items"] = items
    return items


def _maybe_create_fall_alarm(fall, source):
    cooldown = max(5, int(os.getenv("FALL_ALARM_COOLDOWN_SECONDS", "30")))
    now = time.time()
    if now - _fall_alarm_state["last_alarm_at"] < cooldown:
        return

    from .event_api import create_alarm

    create_alarm({
        "cameraId": str(source),
        "eventType": "fall",
        "title": "疑似摔倒",
        "description": f"实时视频检测到疑似摔倒：{fall.get('reason')}",
        "severity": fall.get("severity", "high"),
        "confidence": fall.get("confidence"),
        "detectionData": fall,
    })
    _fall_alarm_state["last_alarm_at"] = now


def _annotate_frame(frame, source):
    known_faces = _known_faces()
    detections = _face_recognizer.recognize_frame(frame, known_faces=known_faces)
    for detection in detections:
        x, y, width, height = detection["box"]
        matched = detection["matched"]
        color = (67, 214, 139) if matched else (64, 167, 255)
        label = detection["name"]
        if detection["distance"] is not None:
            label = f"{label} {detection['confidence']:.0%}"
        _draw_box_label(frame, [x, y, x + width, y + height], label, color, font_size=24)

    falls = _fall_detector.detect_frame(frame)
    for fall in falls:
        label = f"摔倒 {fall['confidence']:.0%}"
        _draw_box_label(frame, fall["box"], label, (42, 60, 229), font_size=26)
        _maybe_create_fall_alarm(fall, source)

    status = f"{_face_recognizer.model_name}  known={len(known_faces)}  detected={len(detections)}  falls={len(falls)}"
    cv2.rectangle(frame, (16, 16), (610, 54), (17, 24, 32), -1)
    cv2.putText(frame, status, (28, 43), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (104, 209, 157), 2, cv2.LINE_AA)
    return frame


def _mjpeg_part(jpeg_bytes):
    return (
        b"--frame\r\n"
        b"Content-Type: image/jpeg\r\n"
        b"Cache-Control: no-cache\r\n\r\n"
        + jpeg_bytes
        + b"\r\n"
    )


def _offline_frame(source, detail):
    import numpy as np

    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    frame[:] = (32, 24, 17)
    cv2.rectangle(frame, (34, 34), (926, 506), (99, 81, 59), 3)
    cv2.putText(frame, "Camera Offline", (64, 155), cv2.FONT_HERSHEY_SIMPLEX, 1.6, (247, 245, 237), 3, cv2.LINE_AA)
    cv2.putText(frame, str(detail)[:68], (64, 225), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 186, 167), 2, cv2.LINE_AA)
    cv2.putText(frame, f"source: {source}"[:72], (64, 285), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (157, 209, 104), 2, cv2.LINE_AA)
    cv2.putText(frame, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), (64, 345), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (157, 209, 104), 2, cv2.LINE_AA)
    ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
    return encoded.tobytes() if ok else b""


def _jpeg_stream(source):
    capture = None
    last_error_at = 0
    while True:
        if capture is None or not capture.isOpened():
            if capture is not None:
                capture.release()
            capture = _open_capture(source)
            if not capture.isOpened():
                now = time.time()
                if now - last_error_at > 5:
                    current_app.logger.warning("Video source is not available: %s", source)
                    last_error_at = now
                offline = _offline_frame(source, "source could not be opened")
                if offline:
                    yield _mjpeg_part(offline)
                time.sleep(1)
                continue

        ok, frame = capture.read()
        if not ok or frame is None:
            capture.release()
            capture = None
            offline = _offline_frame(source, "source opened but no frame was read")
            if offline:
                yield _mjpeg_part(offline)
            time.sleep(0.2)
            continue

        try:
            frame = _annotate_frame(frame, source)
        except Exception as exc:
            current_app.logger.warning("Face annotation failed: %s", exc)

        ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
        if not ok:
            continue

        yield _mjpeg_part(encoded.tobytes())


@stream_bp.get("/demo.mjpg")
def demo_stream():
    return _svg_response("Smart Campus Video", "Demo stream placeholder")


@stream_bp.get("/live.mjpg")
def live_stream():
    source = _resolve_source()
    if cv2 is None:
        return _svg_response(
            "Camera dependency missing",
            "Install opencv-python-headless and restart the backend.",
            status=503,
        )
    return Response(
        stream_with_context(_jpeg_stream(source)),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


@stream_bp.get("/status")
def stream_status():
    source = _resolve_source()
    available = False
    detail = ""
    if cv2 is None:
        detail = "opencv-python-headless is not installed"
    else:
        capture = _open_capture(source)
        available = capture.isOpened()
        if available:
            ok, _frame = capture.read()
            available = bool(ok)
            detail = "frame readable" if available else "source opened but no frame was read"
        else:
            detail = "source could not be opened"
        capture.release()

    return jsonify({
        "code": 0 if available else 503,
        "data": {
            "available": available,
            "source": str(source),
            "detail": detail,
            "feedUrl": current_app.config.get("VIDEO_FEED_URL"),
            "knownFaces": len(_known_faces()) if available else 0,
        },
        "message": "ok" if available else "camera unavailable",
    }), 200 if available else 503
