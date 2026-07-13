import time
from datetime import datetime
import logging
import threading
import cv2
import numpy as np
from flask import Blueprint, Response, request, current_app

logger = logging.getLogger(__name__)

_active_streams = {}
_active_streams_lock = threading.Lock()


def get_active_streams():
    """Return a snapshot of active MJPEG stream counts."""
    with _active_streams_lock:
        return dict(_active_streams)

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


def _generate_fallback_frame(camera_id, url_str, connecting=True):
    # Create a dark slate background with premium aesthetics
    frame = np.zeros((540, 960, 3), dtype=np.uint8)
    for y in range(540):
        c = int(15 + 20 * (1.0 - y / 540.0))
        frame[y, :] = (c + 5, c, c - 2)

    # Draw dual border
    cv2.rectangle(frame, (10, 10), (950, 530), (70, 60, 50), 1)
    cv2.rectangle(frame, (8, 8), (952, 532), (40, 35, 30), 1)

    # Blinking status indicator
    is_on = int(time.time() * 2.0) % 2 == 0
    if connecting:
        status_text = "CONNECTING..."
        color = (0, 165, 255) if is_on else (0, 100, 150)
    else:
        status_text = "OFFLINE"
        color = (0, 0, 255) if is_on else (0, 0, 100)

    cv2.circle(frame, (50, 50), 8, color, -1)
    cv2.putText(frame, f"CAMERA ID: {str(camera_id).upper()}", (75, 57),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (240, 240, 240), 2)
    cv2.putText(frame, status_text, (800, 57),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # Configured url
    cv2.putText(frame, f"Configured URL: {url_str}", (50, 130),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (170, 170, 170), 1)

    # Instructions
    if url_str.startswith("rtmp://") or url_str.startswith("rtsp://"):
        cv2.putText(frame, "Instructions for Mobile / Network Stream:", (50, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        
        cv2.putText(frame, "1. Install Larix Broadcaster or another RTMP push app on your phone", (70, 250),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        cv2.putText(frame, f"2. Configure connection URL/Server: {url_str}", (70, 300),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        cv2.putText(frame, "3. Ensure your phone is connected to the internet/Wi-Fi", (70, 350),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        
        cv2.putText(frame, "4. Start broadcasting in the app to establish the live feed", (70, 400),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    else:
        cv2.putText(frame, "Instructions for Local Webcam:", (50, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
        cv2.putText(frame, f"Webcam index {url_str} is configured", (70, 250),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
        cv2.putText(frame, "Ensure no other app (e.g. Zoom, WeChat) is currently using the camera", (70, 300),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, f"FEED TIME: {time_str}", (50, 495),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)

    return frame


def generate_camera_frames(camera_id, manager):
    last_good_jpeg = None
    last_fallback_time = 0

    with _active_streams_lock:
        _active_streams[camera_id] = _active_streams.get(camera_id, 0) + 1
        active_count = _active_streams[camera_id]
    logger.info(
        f"MJPEG Stream started for {camera_id} "
        f"(active: {active_count}, total threads: {threading.active_count()})"
    )

    try:
        while True:
            pipeline = manager.pipelines.get(camera_id) if manager else None
            jpeg_bytes = None
            sleep_seconds = 0.04

            if pipeline is not None:
                jpeg_bytes = getattr(pipeline, 'latest_jpeg_bytes', None)
                if jpeg_bytes is None and pipeline.latest_processed_frame is not None:
                    with pipeline.frame_lock:
                        frame = pipeline.latest_processed_frame.copy()
                    jpeg_bytes = _frame_to_jpeg_bytes(frame)
            
            if jpeg_bytes is None:
                is_connecting = True
                url_str = ""
                if pipeline is not None:
                    url_str = str(pipeline.url)
                    if getattr(pipeline, "stream_manager", None) is not None:
                        is_connecting = not pipeline.stream_manager.connected
                else:
                    try:
                        from core_cv.pipeline import load_camera_streams
                        streams = load_camera_streams()
                        url_str = str(streams.get(camera_id, ""))
                    except Exception:
                        pass

                now_sec = int(time.time() * 2.0)
                if last_good_jpeg is None or now_sec != last_fallback_time:
                    fallback_frame = _generate_fallback_frame(camera_id, url_str, connecting=is_connecting)
                    last_good_jpeg = _frame_to_jpeg_bytes(fallback_frame)
                    last_fallback_time = now_sec
                
                jpeg_bytes = last_good_jpeg

            if jpeg_bytes is not None:
                yield _mjpeg_chunk(jpeg_bytes)

            time.sleep(sleep_seconds)
    except GeneratorExit:
        logger.info(f"MJPEG Stream for {camera_id} received GeneratorExit.")
    except Exception as e:
        logger.error(f"MJPEG Stream for {camera_id} error: {e}")
    finally:
        with _active_streams_lock:
            _active_streams[camera_id] -= 1
            active_count = _active_streams.get(camera_id, 0)
            if active_count <= 0:
                _active_streams.pop(camera_id, None)
        logger.info(
            f"MJPEG Stream stopped for {camera_id} "
            f"(remaining active: {active_count})"
        )


@stream_bp.get("/<camera_id>.mjpg")
def camera_stream(camera_id):
    if request.method == 'HEAD':
        return Response("", mimetype="multipart/x-mixed-replace; boundary=frame")
    manager = current_app.config.get('pipeline_manager')
    return Response(
        generate_camera_frames(camera_id, manager),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@stream_bp.get("/demo.mjpg")
def demo_stream():
    if request.method == 'HEAD':
        return Response("", mimetype="multipart/x-mixed-replace; boundary=frame")
    manager = current_app.config.get('pipeline_manager')
    return Response(
        generate_camera_frames("cam-1", manager),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@stream_bp.get("/config")
def get_stream_config():
    from core_cv.pipeline import load_camera_streams
    streams = load_camera_streams()
    return {
        "code": 0,
        "message": "ok",
        "data": streams
    }


@stream_bp.post("/cam-1/toggle_source")
def toggle_cam1_source():
    from core_cv.pipeline import load_camera_streams, update_camera_source
    streams = load_camera_streams()
    current_source = str(streams.get("cam-1", ""))
    
    if current_source.startswith("rtmp://"):
        new_source = "0"
    else:
        new_source = "rtmp://39.97.236.134:9090/live/cam01"
        
    update_camera_source("cam-1", new_source)
    return {
        "code": 0,
        "message": "Source updated successfully",
        "data": {
            "camera_id": "cam-1",
            "source": new_source
        }
    }
