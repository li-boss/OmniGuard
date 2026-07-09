import time
from datetime import datetime
import cv2
import numpy as np
from flask import Blueprint, Response

stream_bp = Blueprint("streams", __name__)


def generate_demo_frames():
    from core_cv.pipeline import CameraPipelineManager
    manager = CameraPipelineManager()

    while True:
        # Check if there is an active local camera pipeline running
        # Try to match 'cam-1' (which is the default Selected Camera) or take the first available
        pipeline = manager.pipelines.get('cam-1') or (list(manager.pipelines.values())[0] if manager.pipelines else None)
        
        if pipeline and pipeline.latest_processed_frame is not None:
            # Retrieve the latest processed frame from the real webcam pipeline (already drawn with overlays)
            frame_to_stream = pipeline.latest_processed_frame
            ret, jpeg = cv2.imencode('.jpg', frame_to_stream)
            if ret:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
                # 25 FPS sleep time for real webcam stream
                time.sleep(0.04)
                continue

        # FALLBACK: Create a simulated techy dark demo frame (960x540)
        frame = np.zeros((540, 960, 3), dtype=np.uint8)
        frame[:] = (20, 15, 10)  # Dark background
        
        # 1. Draw border
        cv2.rectangle(frame, (20, 20), (940, 520), (60, 50, 40), 2)
        
        # 2. Camera Title
        cv2.putText(frame, "CAM-01: CAMPUS MAIN ENTRANCE (DEMO)", (40, 60), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (240, 240, 240), 2)
        
        # 3. Live Indicator with blinking red dot
        is_even = int(time.time() * 2) % 2 == 0
        circle_color = (0, 0, 255) if is_even else (0, 0, 100)
        cv2.circle(frame, (900, 52), 8, circle_color, -1)
        cv2.putText(frame, "LIVE", (840, 59), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (245, 245, 245), 2)
        
        # 4. Running Clock
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, f"TIME: {time_str}", (40, 490), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 220, 100), 2)
        
        # 5. Draw animated HUD bounding box tracking a target
        offset = int(180 * np.sin(time.time() * 1.5))
        x1, y1 = 420 + offset, 180
        x2, y2 = x1 + 130, y1 + 240
        
        # Draw bounding box (green)
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
        cv2.putText(frame, "Person: 98.4%", (x1, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 1)
        
        # Draw face detection sub-box
        fx1, fy1 = x1 + 35, y1 + 20
        fx2, fy2 = fx1 + 60, fy1 + 65
        cv2.rectangle(frame, (fx1, fy1), (fx2, fy2), (255, 180, 0), 2)
        cv2.putText(frame, "Student: Zhang San", (fx1 - 15, fy1 - 8), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 180, 0), 1)

        # 6. Draw active electronic fence polygon (simulated)
        pts = np.array([[100, 350], [300, 250], [700, 250], [860, 350]], np.int32)
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(frame, [pts], True, (0, 160, 255), 2)
        cv2.putText(frame, "E-FENCE ZONE A", (110, 340), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 160, 255), 1)
        
        # Encode as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            continue
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        
        # Maintain 10 FPS for fallback
        time.sleep(0.1)


@stream_bp.get("/demo.mjpg")
def demo_stream():
    return Response(generate_demo_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")
