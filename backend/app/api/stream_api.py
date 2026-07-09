from datetime import datetime
import html
import os
import time

from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context


stream_bp = Blueprint("streams", __name__)


try:
    import cv2
except ImportError:  # pragma: no cover - exercised only when optional runtime dep is absent
    cv2 = None


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
        },
        "message": "ok" if available else "camera unavailable",
    }), 200 if available else 503
