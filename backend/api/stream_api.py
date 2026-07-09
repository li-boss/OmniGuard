import time
from datetime import datetime
import cv2
import numpy as np
from flask import Blueprint, Response, request

stream_bp = Blueprint("streams", __name__)


def _frame_to_jpeg_bytes(frame):
    if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
        return None
    if frame.dtype != np.uint8:
        frame = np.clip(frame, 0, 255).astype(np.uint8)
    if len(frame.shape) == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    elif len(frame.shape) != 3 or frame.shape[2] < 3:
        return None
    elif frame.shape[2] > 3:
        frame = frame[:, :, :3]

    frame = np.ascontiguousarray(frame)
    ok, jpeg = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        return None
    return jpeg.tobytes()


def _mjpeg_chunk(jpeg_bytes):
    return (
        b'--frame\r\n'
        b'Content-Type: image/jpeg\r\n'
        b'Content-Length: ' + str(len(jpeg_bytes)).encode('ascii') + b'\r\n\r\n' +
        jpeg_bytes + b'\r\n'
    )


def _latest_pipeline_frame():
    from core_cv.pipeline import CameraPipelineManager

    manager = CameraPipelineManager()
    pipeline = manager.pipelines.get('cam-1') or (list(manager.pipelines.values())[0] if manager.pipelines else None)
    if pipeline is None or pipeline.latest_processed_frame is None:
        return None

    lock = getattr(pipeline, 'frame_lock', None)
    if lock:
        with lock:
            return pipeline.latest_processed_frame.copy()
    return pipeline.latest_processed_frame.copy()


def _demo_frame():
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    frame[:] = (20, 15, 10)

    cv2.rectangle(frame, (20, 20), (940, 520), (60, 50, 40), 2)
    cv2.putText(frame, "CAM-01: CAMPUS MAIN ENTRANCE (DEMO)", (40, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 240, 240), 2)

    is_even = int(time.time() * 2) % 2 == 0
    circle_color = (0, 0, 255) if is_even else (0, 0, 100)
    cv2.circle(frame, (900, 52), 8, circle_color, -1)
    cv2.putText(frame, "LIVE", (840, 59),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (245, 245, 245), 2)

    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"TIME: {time_str}", (40, 490),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 220, 100), 2)

    offset = int(180 * np.sin(time.time() * 1.5))
    x1, y1 = 420 + offset, 180
    x2, y2 = x1 + 130, y1 + 240

    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
    cv2.putText(frame, "Person: 98.4%", (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 1)

    fx1, fy1 = x1 + 35, y1 + 20
    fx2, fy2 = fx1 + 60, fy1 + 65
    cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (255, 180, 0), 2)
    cv2.putText(frame, "Student: Zhang San", (fx1 - 15, fy1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 180, 0), 1)

    pts = np.array([[100, 350], [300, 250], [700, 250], [860, 350]], np.int32)
    pts = pts.reshape((-1, 1, 2))
    cv2.polylines(frame, [pts], True, (0, 160, 255), 2)
    cv2.putText(frame, "E-FENCE ZONE A", (110, 340),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 160, 255), 1)

    return frame


def generate_demo_frames():
    last_good_jpeg = None

    while True:
        frame = _latest_pipeline_frame()
        sleep_seconds = 0.04
        if frame is None:
            frame = _demo_frame()
            sleep_seconds = 0.1

        jpeg_bytes = _frame_to_jpeg_bytes(frame)
        if jpeg_bytes is None:
            jpeg_bytes = last_good_jpeg
        else:
            last_good_jpeg = jpeg_bytes

        if jpeg_bytes is not None:
            yield _mjpeg_chunk(jpeg_bytes)

        time.sleep(sleep_seconds)


@stream_bp.get("/demo.mjpg")
def demo_stream():
    if request.method == 'HEAD':
        return Response("", mimetype="multipart/x-mixed-replace; boundary=frame")
    return Response(
        generate_demo_frames(),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )