from .model_loader import ModelLoader
from .rule_engine import RuleEngine
from .yolo_detector import YOLODetector
from ..models import Zone


class DetectionPipeline:
    def __init__(self):
        self.model_loader = ModelLoader()
        self.detector = YOLODetector(self.model_loader.get_yolo())
        self.rule_engine = RuleEngine()

    def process_frame(self, camera_id, frame):
        from ..api.event_api import create_alarm

        detections = self.detector.detect_frame(frame)
        zones = Zone.query.filter_by(camera_id=str(camera_id), enabled=True).all()
        alarms = []

        for detection in detections:
            hits = self.rule_engine.evaluate_detection(detection, zones)
            for hit in hits:
                alarm = create_alarm({
                    "cameraId": str(camera_id),
                    "zoneId": hit["zoneId"],
                    "eventType": hit["ruleType"],
                    "title": f"{hit['zoneName']}触发{hit['ruleType']}",
                    "description": "检测管线自动生成告警",
                    "severity": detection.get("severity", "medium"),
                    "confidence": detection.get("confidence"),
                    "snapshotUrl": detection.get("snapshotUrl"),
                })
                alarms.append(alarm.to_dict())
        return {"detections": detections, "alarms": alarms}
