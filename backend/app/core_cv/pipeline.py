import queue
import threading
import time

from .face_recognizer import FaceRecognizer
from .fall_detector import FallDetector
from .model_loader import ModelLoader
from .rule_engine import RuleEngine
from .stream_manager import StreamManager
from .yolo_detector import YOLODetector
from ..models import Zone


alarm_queue = queue.Queue(maxsize=200)


def iou(box1, box2):
    xi1 = max(box1[0], box2[0])
    yi1 = max(box1[1], box2[1])
    xi2 = min(box1[2], box2[2])
    yi2 = min(box1[3], box2[3])
    inter_area = max(0, xi2 - xi1) * max(0, yi2 - yi1)
    box1_area = (box1[2] - box1[0]) * (box1[3] - box1[1])
    box2_area = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = box1_area + box2_area - inter_area
    return 0.0 if union_area == 0 else inter_area / union_area


class SimpleTracker:
    def __init__(self, max_lost_seconds=2.0):
        self.tracks = {}
        self.next_id = 1
        self.max_lost_seconds = max_lost_seconds

    def update(self, detections):
        now = time.time()
        for object_id, track in list(self.tracks.items()):
            if now - track["last_seen"] > self.max_lost_seconds:
                self.tracks.pop(object_id, None)

        matched_detections = set()
        for object_id in sorted(self.tracks, key=lambda key: self.tracks[key]["last_seen"], reverse=True):
            track = self.tracks[object_id]
            best_iou = 0.0
            best_idx = -1
            for idx, detection in enumerate(detections):
                if idx in matched_detections:
                    continue
                score = iou(track["box"], detection)
                if score > best_iou:
                    best_iou = score
                    best_idx = idx
            if best_iou >= 0.3 and best_idx != -1:
                self.tracks[object_id] = {"box": detections[best_idx], "last_seen": now}
                matched_detections.add(best_idx)

        for idx, detection in enumerate(detections):
            if idx in matched_detections:
                continue
            object_id = self.next_id
            self.next_id += 1
            self.tracks[object_id] = {"box": detection, "last_seen": now}

        return self.tracks.copy()


class DetectionPipeline:
    def __init__(self):
        self.model_loader = ModelLoader()
        self.detector = YOLODetector(self.model_loader.get_yolo())
        self.fall_detector = FallDetector(confirm_frames=1, use_hog=False)
        self.rule_engine = RuleEngine()

    def process_frame(self, camera_id, frame):
        from ..api.event_api import create_alarm

        detections = self.detector.detect_frame(frame)
        zones = Zone.query.filter_by(camera_id=str(camera_id), enabled=True).all()
        alarms = []

        for fall in self.fall_detector.detect_frame(frame, detections=detections):
            alarm = create_alarm({
                "cameraId": str(camera_id),
                "eventType": "fall",
                "title": "疑似摔倒",
                "description": "Fall detector generated alarm",
                "severity": fall.get("severity", "high"),
                "confidence": fall.get("confidence"),
                "detectionData": fall,
            })
            alarms.append(alarm.to_dict())

        for detection in detections:
            hits = self.rule_engine.evaluate_detection(detection, zones)
            for hit in hits:
                alarm = create_alarm({
                    "cameraId": str(camera_id),
                    "zoneId": hit["zoneId"],
                    "eventType": hit["ruleType"],
                    "title": f"{hit['zoneName']} {hit['ruleType']}",
                    "description": "Detection pipeline generated alarm",
                    "severity": detection.get("severity", "medium"),
                    "confidence": detection.get("confidence"),
                    "snapshotUrl": detection.get("snapshotUrl"),
                    "detectionData": detection,
                })
                alarms.append(alarm.to_dict())
        return {"detections": detections, "alarms": alarms}


class AlarmWorker(threading.Thread):
    def __init__(self, app):
        super().__init__(name="AlarmWorkerThread", daemon=True)
        self.app = app
        self.running = True

    def run(self):
        while self.running:
            try:
                item = alarm_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            self.save_and_broadcast_alarm(item)
            alarm_queue.task_done()

    def save_and_broadcast_alarm(self, item):
        from ..api.event_api import create_alarm

        with self.app.app_context():
            return create_alarm({
                "cameraId": item.get("camera_id"),
                "eventType": item.get("alarm_type", "intrusion"),
                "title": item.get("alarm_type", "intrusion"),
                "description": item.get("description"),
                "severity": item.get("level", "medium"),
                "snapshotUrl": item.get("snapshot_url"),
                "detectionData": item.get("coordinate"),
            })


class CameraPipeline:
    def __init__(self, camera_id, url, app, face_recognizer=None, rule_engine=None):
        self.camera_id = str(camera_id)
        self.url = url
        self.app = app
        self.face_recognizer = face_recognizer or FaceRecognizer(app=app)
        self.rule_engine = rule_engine or RuleEngine()
        self.stream_manager = StreamManager(url)
        self.yolo_detector = YOLODetector()
        self.fall_detector = FallDetector(confirm_frames=2, use_hog=False)
        self.tracker = SimpleTracker()
        self.zones = []

    def update_zones(self, zones):
        self.zones = zones

    def process_frame(self):
        frame = self.stream_manager.get_latest_frame()
        if frame is None:
            return

        detections = self.yolo_detector.detect(frame)
        for fall in self.fall_detector.detect_frame(frame, detections=detections):
            self._queue_fall_alarm(fall)

        tracks = self.tracker.update([detection["box"] for detection in detections if "box" in detection])
        for detection in detections:
            box = detection.get("box")
            if not box:
                continue
            object_id = None
            for candidate_id, track in tracks.items():
                if iou(track["box"], box) > 0.8:
                    object_id = candidate_id
                    break
            if object_id is None:
                continue

            box_norm = detection.get("box_norm") or box
            for zone in self.zones:
                if not zone.get("enabled", True):
                    continue
                should_trigger, duration = self.rule_engine.evaluate_stay(object_id, box_norm, zone)
                if should_trigger:
                    self._queue_alarm(detection, zone, duration)

    def _queue_alarm(self, detection, zone, duration):
        alarm_data = {
            "alarm_type": zone.get("rule_type") or zone.get("ruleType") or "intrusion",
            "level": detection.get("severity", "medium"),
            "camera_id": self.camera_id,
            "coordinate": {"box": detection.get("box_norm") or detection.get("box"), "duration": duration},
            "description": f"Object stayed in {zone.get('name', 'zone')} for {duration:.1f}s",
        }
        try:
            alarm_queue.put_nowait(alarm_data)
        except queue.Full:
            try:
                alarm_queue.get_nowait()
            except queue.Empty:
                pass
            alarm_queue.put_nowait(alarm_data)

    def _queue_fall_alarm(self, fall):
        alarm_data = {
            "alarm_type": "fall",
            "level": fall.get("severity", "high"),
            "camera_id": self.camera_id,
            "coordinate": {
                "box": fall.get("box_norm") or fall.get("box"),
                "reason": fall.get("reason"),
                "confidence": fall.get("confidence"),
            },
            "description": "Fall detector generated alarm",
        }
        try:
            alarm_queue.put_nowait(alarm_data)
        except queue.Full:
            try:
                alarm_queue.get_nowait()
            except queue.Empty:
                pass
            alarm_queue.put_nowait(alarm_data)

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
                if app is not None:
                    self.app = app
                return
            self.app = app
            self.face_recognizer = FaceRecognizer(app=app)
            self.rule_engine = RuleEngine()
            self.pipelines = {}
            self.dirty_cameras = set()
            self.running = False
            self._runner_thread = None
            self._alarm_worker = None
            self._initialized = True

    def mark_dirty(self, camera_id):
        with self._lock:
            self.dirty_cameras.add(str(camera_id))

    def reload_dirty_pipelines(self):
        if not self.app or not self.dirty_cameras:
            return
        with self.app.app_context():
            dirty_ids = list(self.dirty_cameras)
            self.dirty_cameras.clear()
            for camera_id in dirty_ids:
                zones = Zone.query.filter_by(camera_id=str(camera_id), enabled=True).all()
                if not zones:
                    pipeline = self.pipelines.pop(str(camera_id), None)
                    if pipeline:
                        pipeline.release()
                    continue
                serialized_zones = [
                    {
                        "id": zone.id,
                        "camera_id": zone.camera_id,
                        "name": zone.name,
                        "polygon": zone.get_points(),
                        "stay_seconds": getattr(zone, "stay_seconds", 5),
                        "enabled": zone.enabled,
                        "rule_type": zone.rule_type,
                    }
                    for zone in zones
                ]
                pipeline = self.pipelines.get(str(camera_id))
                if pipeline is None:
                    pipeline = CameraPipeline(str(camera_id), str(camera_id), self.app, self.face_recognizer, self.rule_engine)
                    self.pipelines[str(camera_id)] = pipeline
                pipeline.update_zones(serialized_zones)

    def start(self):
        if self.running or not self.app:
            return
        self.running = True
        self._alarm_worker = AlarmWorker(self.app)
        self._alarm_worker.start()

    def stop(self):
        self.running = False
        if self._alarm_worker:
            self._alarm_worker.running = False
            self._alarm_worker.join(timeout=2.0)
        for pipeline in list(self.pipelines.values()):
            pipeline.release()
        self.pipelines.clear()
