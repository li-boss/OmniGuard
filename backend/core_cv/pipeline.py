import os
import time
import queue
import threading
import logging
import cv2
import json
import numpy as np
from datetime import datetime

from models import db, AlertZone, AlarmEvent
from config import Config
from .stream_manager import StreamManager
from .yolo_detector import YoloDetector
from .face_recognizer import FaceRecognizer
from .rule_engine import RuleEngine

logger = logging.getLogger(__name__)

# Global alarm queue, thread-safe
alarm_queue = queue.Queue(maxsize=200)

def resolve_camera_url(camera_id):
    """Resolve camera_id to stream source URL or local webcam index."""
    if (camera_id.startswith("rtsp://") or 
        camera_id.startswith("rtmp://") or 
        camera_id.startswith("http://") or 
        camera_id.startswith("https://") or 
        camera_id.isdigit()):
        return int(camera_id) if camera_id.isdigit() else camera_id
        
    env_url = os.getenv(f"STREAM_URL_{camera_id.upper()}")
    if env_url:
        return env_url
        
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "camera_streams.json")
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r') as f:
                mapping = json.load(f)
            if camera_id in mapping:
                val = mapping[camera_id]
                return int(val) if str(val).isdigit() else val
        except Exception as e:
            logger.error(f"Error reading camera_streams.json: {e}")
            
    # Default fallback: try 0 for local webcam
    return 0

def iou(box1, box2):
    """Calculate Intersection over Union (IoU) of two boxes [x1, y1, x2, y2]."""
    xi1 = max(box1[0], box2[0])
    yi1 = max(box1[1], box2[1])
    xi2 = min(box1[2], box2[2])
    yi2 = min(box1[3], box2[3])
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - inter_area
    if union_area == 0:
        return 0.0
    return inter_area / union_area

class SimpleTracker:
    def __init__(self, max_lost_seconds=2.0):
        self.tracks = {}  # object_id -> {"box": [x1,y1,x2,y2], "last_seen": ts}
        self.next_id = 1
        self.max_lost_seconds = max_lost_seconds

    def update(self, detections):
        """Update tracker with new bounding boxes. Returns current active tracks."""
        now = time.time()
        
        # Clean up old tracks
        for obj_id, track in list(self.tracks.items()):
            if now - track["last_seen"] > self.max_lost_seconds:
                self.tracks.pop(obj_id, None)
                
        updated_tracks = {}
        matched_detections = set()
        
        # Sort current tracks by last_seen descending to match fresher tracks first
        sorted_track_ids = sorted(self.tracks.keys(), key=lambda k: self.tracks[k]["last_seen"], reverse=True)
        
        for obj_id in sorted_track_ids:
            track = self.tracks[obj_id]
            best_iou = 0.0
            best_idx = -1
            
            for idx, det in enumerate(detections):
                if idx in matched_detections:
                    continue
                score = iou(track["box"], det)
                if score > best_iou:
                    best_iou = score
                    best_idx = idx
                    
            if best_iou >= 0.3 and best_idx != -1:
                self.tracks[obj_id] = {
                    "box": detections[best_idx],
                    "last_seen": now
                }
                updated_tracks[obj_id] = self.tracks[obj_id]
                matched_detections.add(best_idx)
                
        # Create new tracks for unmatched detections
        for idx, det in enumerate(detections):
            if idx in matched_detections:
                continue
            obj_id = self.next_id
            self.next_id += 1
            self.tracks[obj_id] = {
                "box": det,
                "last_seen": now
            }
            updated_tracks[obj_id] = self.tracks[obj_id]
            
        return self.tracks.copy()


class AlarmWorker(threading.Thread):
    def __init__(self, app):
        super().__init__(name="AlarmWorkerThread", daemon=True)
        self.app = app
        self.running = True

    def run(self):
        logger.info("AlarmWorker thread started.")
        while self.running:
            try:
                # Block for 1 second waiting for alarm items
                try:
                    item = alarm_queue.get(timeout=1.0)
                except queue.Empty:
                    continue
                
                self.save_and_broadcast_alarm(item)
                alarm_queue.task_done()
            except Exception as e:
                logger.error(f"Error in AlarmWorker loop: {e}")
        logger.info("AlarmWorker thread stopped.")

    def save_and_broadcast_alarm(self, item):
        with self.app.app_context():
            try:
                # 1. Create snapshot path and save image
                static_dir = os.path.join(self.app.root_path, 'static', 'snapshots')
                os.makedirs(static_dir, exist_ok=True)
                
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{item['camera_id']}_{timestamp_str}.jpg"
                abs_path = os.path.join(static_dir, filename)
                rel_path = f"/static/snapshots/{filename}"
                
                cv2.imwrite(abs_path, item["snapshot_frame"])
                logger.info(f"Snapshot saved to {abs_path}")
                
                # 2. Save AlarmEvent to database
                event = AlarmEvent(
                    alarm_type=item["alarm_type"],
                    level=item["level"],
                    camera_id=item["camera_id"],
                    coordinate=item["coordinate"],
                    status="pending",
                    snapshot_path=rel_path,
                    created_at=datetime.utcnow()
                )
                db.session.add(event)
                db.session.commit()
                logger.info(f"AlarmEvent saved to DB: ID {event.id}")
                
                # 3. Emit via SocketIO
                try:
                    from services.ws_handler import emit_alarm
                    alarm_payload = {
                        "id": event.id,
                        "alarm_type": event.alarm_type,
                        "level": event.level,
                        "camera_id": event.camera_id,
                        "coordinate": event.coordinate,
                        "status": event.status,
                        "snapshot_path": event.snapshot_path,
                        "created_at": event.created_at.isoformat() + 'Z',
                        "name": item["name"]
                    }
                    emit_alarm(alarm_payload)
                    logger.info("Alarm emitted via WebSocket.")
                except Exception as wse:
                    logger.error(f"Failed to emit alarm via WebSocket: {wse}")
                
                # 4. Send DingTalk notification
                if Config.DINGTALK_WEBHOOK:
                    try:
                        from services.notification_svc import send_dingtalk_alarm
                        payload = {
                            "msgtype": "markdown",
                            "markdown": {
                                "title": f"智慧校园告警: {item['alarm_type']}",
                                "text": f"### 智慧校园安全告警\n"
                                        f"- **告警类型**: {item['alarm_type']}\n"
                                        f"- **告警级别**: {item['level']}\n"
                                        f"- **摄像头**: {item['camera_id']}\n"
                                        f"- **检测人员**: {item['name']}\n"
                                        f"- **发生时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            }
                        }
                        send_dingtalk_alarm(Config.DINGTALK_WEBHOOK, payload)
                        logger.info("DingTalk alarm notification sent.")
                    except Exception as dte:
                        logger.error(f"Failed to send DingTalk notification: {dte}")
                        
            except Exception as e:
                db.session.rollback()
                logger.error(f"Error saving/broadcasting alarm: {e}")


class CameraPipeline:
    def __init__(self, camera_id, url, app, face_recognizer, rule_engine):
        self.camera_id = camera_id
        self.url = url
        self.app = app
        self.face_recognizer = face_recognizer
        self.rule_engine = rule_engine
        
        self.stream_manager = StreamManager(url)
        self.yolo_detector = YoloDetector()
        self.tracker = SimpleTracker()
        self.zones = []
        
        self.last_clean_time = time.time()
        self.latest_processed_frame = None

    def update_zones(self, zones):
        self.zones = zones
        logger.info(f"Updated {len(zones)} zones for camera {self.camera_id}")

    def process_frame(self):
        # Read latest frame
        frame = self.stream_manager.get_latest_frame()
        if frame is None:
            return
            
        # Periodically clean up expired tracker / rule states (every 10 seconds)
        now = time.time()
        if now - self.last_clean_time > 10.0:
            self.rule_engine.cleanup_expired_states()
            self.last_clean_time = now

        # Draw zones and other stuff on drawn_frame
        drawn_frame = frame.copy()
        h, w = frame.shape[:2]
        
        # Draw zones
        for zone in self.zones:
            pts = []
            for p in zone.get("polygon", []):
                px = int(p["x"] * w) if p["x"] <= 1.0 else int(p["x"])
                py = int(p["y"] * h) if p["y"] <= 1.0 else int(p["y"])
                pts.append([px, py])
            if pts:
                pts_arr = np.array(pts, np.int32).reshape((-1, 1, 2))
                cv2.polylines(drawn_frame, [pts_arr], True, (0, 165, 255), 2)
                cv2.putText(drawn_frame, zone.get("name", "Zone"), (pts[0][0], pts[0][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 1)

        # 1. Person Detection using YOLO
        detections = self.yolo_detector.detect(frame)
        if detections:
            # 2. Update simple tracker to get consistent object IDs
            person_boxes = [det["box"] for det in detections]
            tracks = self.tracker.update(person_boxes)

            # Map tracker outputs to original detections by box match (using IoU)
            for det in detections:
                det_box = det["box"]
                det["object_id"] = None
                best_iou = 0.0
                for obj_id, track in tracks.items():
                    score = iou(track["box"], det_box)
                    if score > best_iou:
                        best_iou = score
                        if score > 0.8:
                            det["object_id"] = obj_id

            # 3. Process each person detection
            for det in detections:
                obj_id = det["object_id"]
                if obj_id is None:
                    continue

                # Run Face detection and recognition inside the person crop
                face_found, face_box_norm, name, user_id, dist = self.face_recognizer.detect_and_recognize_in_person(
                    frame, det["box"]
                )

                # Draw person box
                box = det["box"]
                cv2.rectangle(drawn_frame, (int(box[0]), int(box[1])), (int(box[2]), int(box[3])), (0, 255, 0), 2)
                cv2.putText(drawn_frame, f"Person (ID {obj_id})", (int(box[0]), int(box[1]) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 1)

                # Draw face box if found
                if face_found and face_box_norm:
                    fx1 = int(face_box_norm[0] * w)
                    fy1 = int(face_box_norm[1] * h)
                    fx2 = int(face_box_norm[2] * w)
                    fy2 = int(face_box_norm[3] * h)
                    cv2.rectangle(drawn_frame, (fx1, fy1), (fx2, fy2), (255, 180, 0), 2)
                    cv2.putText(drawn_frame, name, (fx1, fy1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 1)

                # 4. Evaluate Alert Zones
                for zone in self.zones:
                    if not zone.get("enabled", True):
                        continue

                    should_trigger, duration = self.rule_engine.evaluate_stay(
                        object_id=obj_id,
                        box_norm=det["box_norm"],
                        zone=zone
                    )

                    if should_trigger:
                        logger.warning(f"Stay alert triggered for Object {obj_id} in Zone {zone['name']} (duration: {duration:.1f}s)")
                        
                        coordinate_info = {
                            "person_box": det["box_norm"],
                            "face_box": face_box_norm if face_found else None
                        }
                        
                        alarm_data = {
                            "alarm_type": "electronic_fence",
                            "level": "medium" if name != "Stranger" else "high",
                            "camera_id": self.camera_id,
                            "coordinate": coordinate_info,
                            "snapshot_frame": frame.copy(),
                            "name": name
                        }
                        
                        # Safe put in queue
                        try:
                            alarm_queue.put_nowait(alarm_data)
                        except queue.Full:
                            try:
                                alarm_queue.get_nowait()
                            except queue.Empty:
                                pass
                            alarm_queue.put_nowait(alarm_data)

        # Save to latest_processed_frame
        self.latest_processed_frame = drawn_frame

    def release(self):
        self.stream_manager.release()


class CameraPipelineManager:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, app=None):
        with self._lock:
            if self._initialized:
                return
            self.app = app
            self.face_recognizer = FaceRecognizer(app=app)
            self.rule_engine = RuleEngine()
            
            # Map of camera_id -> CameraPipeline
            self.pipelines = {}
            
            self.dirty_cameras = set()
            self.running = False
            self._runner_thread = None
            self._alarm_worker = None
            self._initialized = True

    def mark_dirty(self, camera_id):
        """Mark a camera's configuration as dirty so it gets reloaded in the next cycle."""
        with self._lock:
            self.dirty_cameras.add(camera_id)
            logger.info(f"Camera {camera_id} marked dirty for configuration reload.")

    def reload_dirty_pipelines(self):
        """Query DB and update or create pipelines for dirty cameras."""
        if not self.dirty_cameras:
            return

        with self.app.app_context():
            with self._lock:
                # Copy and clear dirty cameras set
                dirty_ids = list(self.dirty_cameras)
                self.dirty_cameras.clear()
                
            for camera_id in dirty_ids:
                try:
                    # Get enabled zones for this camera
                    zones = AlertZone.query.filter_by(camera_id=camera_id, enabled=True).all()
                    
                    if not zones:
                        # No active zones, release pipeline if exists
                        if camera_id in self.pipelines:
                            logger.info(f"No active zones for camera {camera_id}. Releasing pipeline.")
                            pipeline = self.pipelines.pop(camera_id)
                            pipeline.release()
                        continue

                    # Serialize zones for rule engine
                    serialized_zones = []
                    for zone in zones:
                        serialized_zones.append({
                            "id": zone.id,
                            "camera_id": zone.camera_id,
                            "name": zone.name,
                            "polygon": zone.polygon,
                            "stay_seconds": zone.stay_seconds,
                            "enabled": zone.enabled
                        })

                    if camera_id in self.pipelines:
                        self.pipelines[camera_id].update_zones(serialized_zones)
                    else:
                        # Resolve URL
                        url = resolve_camera_url(camera_id)
                        logger.info(f"Creating new pipeline for camera {camera_id} with source {url}")
                        
                        pipeline = CameraPipeline(
                            camera_id=camera_id,
                            url=url,
                            app=self.app,
                            face_recognizer=self.face_recognizer,
                            rule_engine=self.rule_engine
                        )
                        pipeline.update_zones(serialized_zones)
                        self.pipelines[camera_id] = pipeline
                        
                except Exception as e:
                    logger.error(f"Error reloading pipeline for camera {camera_id}: {e}")

    def initialize_pipelines(self):
        """Find all cameras that have alert zones and load them initially."""
        try:
            with self.app.app_context():
                # Get unique camera_ids from AlertZone
                camera_ids = [r[0] for r in db.session.query(AlertZone.camera_id).distinct().all()]
                
                with self._lock:
                    self.dirty_cameras.update(camera_ids)
                    
            self.reload_dirty_pipelines()
        except Exception as e:
            logger.warning(f"Failed to initialize pipelines (database tables may not exist yet): {e}")

    def start(self):
        """Start the pipeline execution loop and the database worker thread."""
        with self._lock:
            if self.running:
                logger.warning("Pipeline manager is already running.")
                return
                
            self.running = True
            
            # Start database writing worker
            self._alarm_worker = AlarmWorker(self.app)
            self._alarm_worker.start()
            
            # Load registered faces initially
            self.face_recognizer.reload_known_faces()
            
            # Load initial pipelines
            self.initialize_pipelines()
            
            # Start core CV processing loop in background
            self._runner_thread = threading.Thread(target=self._run_loop, name="CVPipelineRunnerThread", daemon=True)
            self._runner_thread.start()
            logger.info("CameraPipelineManager started successfully.")

    def _run_loop(self):
        logger.info("Core CV processing loop started.")
        while self.running:
            try:
                # 1. Reload configurations if any camera was marked dirty
                self.reload_dirty_pipelines()
                
                # 2. Round-Robin processing across all camera pipelines
                # Get a snapshot of current pipelines to avoid dictionary modification issues
                current_pipelines = list(self.pipelines.values())
                
                if not current_pipelines:
                    # No active pipelines, sleep longer
                    time.sleep(0.5)
                    continue

                for pipeline in current_pipelines:
                    if not self.running:
                        break
                    pipeline.process_frame()
                    
                # Short sleep to prevent 100% CPU thread utilization when cameras are idle
                time.sleep(0.005)
                
            except Exception as e:
                logger.error(f"Exception in core CV runner loop: {e}")
                time.sleep(1.0)
                
        logger.info("Core CV processing loop stopped.")

    def stop(self):
        """Gracefully shut down all running pipelines and threads."""
        logger.info("Stopping CameraPipelineManager...")
        self.running = False
        
        if self._runner_thread is not None:
            self._runner_thread.join(timeout=3.0)
            
        if self._alarm_worker is not None:
            self._alarm_worker.running = False
            self._alarm_worker.join(timeout=3.0)
            
        # Release all video captures
        for camera_id, pipeline in list(self.pipelines.items()):
            try:
                pipeline.release()
            except Exception as e:
                logger.error(f"Error releasing pipeline for camera {camera_id}: {e}")
                
        self.pipelines.clear()
        logger.info("CameraPipelineManager stopped successfully.")
