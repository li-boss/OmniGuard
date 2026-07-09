import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.core_cv.face_recognizer import FaceRecognizer, SFACE_FEATURE_DIM
from app.core_cv.liveness_detector import LivenessDetector
from app.core_cv.pipeline import CameraPipelineManager, DetectionPipeline, SimpleTracker, iou
from app.core_cv.rule_engine import RuleEngine
from app.extensions import db
from app.models import FaceRecord


class CVPipelineTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "DEFAULT_ADMIN_USER": "admin",
            "DEFAULT_ADMIN_PASSWORD": "admin123",
            "JWT_SECRET_KEY": "test-secret",
        })
        self.client = self.app.test_client()
        login = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
        })
        self.headers = {"Authorization": f"Bearer {login.json['data']['token']}"}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        manager = CameraPipelineManager()
        with manager._lock:
            manager.pipelines.clear()
            manager.dirty_cameras.clear()

    def test_iou_and_tracker(self):
        self.assertAlmostEqual(iou([0, 0, 10, 10], [5, 5, 15, 15]), 25 / 175)
        tracker = SimpleTracker(max_lost_seconds=0.2)
        tracks = tracker.update([[10, 10, 50, 50]])
        self.assertIn(1, tracks)
        tracks = tracker.update([[12, 12, 52, 52]])
        self.assertIn(1, tracks)
        time.sleep(0.25)
        self.assertEqual(tracker.update([]), {})

    def test_rule_engine_stay_detection(self):
        engine = RuleEngine(alarm_cooldown_seconds=30)
        zone = {
            "id": 1,
            "polygon": [{"x": 0, "y": 0}, {"x": 1, "y": 0}, {"x": 1, "y": 1}, {"x": 0, "y": 1}],
            "stay_seconds": 1,
        }
        self.assertTrue(engine.point_in_polygon((0.5, 0.5), zone["polygon"]))
        self.assertFalse(engine.evaluate_stay(1, [0.1, 0.1, 0.3, 0.3], zone)[0])
        with patch("app.core_cv.rule_engine.time.time", side_effect=[time.time() + 2]):
            should_trigger, duration = engine.evaluate_stay(1, [0.1, 0.1, 0.3, 0.3], zone)
        self.assertTrue(should_trigger)
        self.assertGreaterEqual(duration, 1)

    def test_detection_pipeline_creates_alarm(self):
        zone = self.client.post("/api/zones", headers=self.headers, json={
            "cameraId": "cam-1",
            "name": "Gate",
            "points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}],
        })
        self.assertEqual(zone.status_code, 201)

        with self.app.app_context():
            result = DetectionPipeline().process_frame("cam-1", {
                "detections": [{
                    "bbox": [10, 10, 20, 20],
                    "severity": "high",
                    "confidence": 0.9,
                }],
            })
        self.assertEqual(len(result["alarms"]), 1)
        self.assertEqual(result["alarms"][0]["cameraId"], "cam-1")

    def test_face_and_liveness_helpers(self):
        recognizer = FaceRecognizer()
        feature = recognizer.extract_feature("data:image/jpeg;base64,ZmFrZQ==")
        self.assertIsInstance(feature, list)
        self.assertEqual(len(feature), SFACE_FEATURE_DIM)
        self.assertTrue(recognizer.compare(feature, feature)["matched"])
        self.assertEqual(recognizer.detect_and_recognize_in_person(None, [0, 0, 1, 1])[2], "Stranger")

        detector = LivenessDetector()
        self.assertEqual(detector.is_live(None), (False, 0.0))
        self.assertEqual(detector.is_live({"isLive": True}), (True, 1.0))

    def test_register_face_rejects_image_without_detectable_face(self):
        result = self.client.post("/api/faces/register", headers=self.headers, json={
            "studentId": "S001",
            "name": "Test User",
            "image": "data:image/jpeg;base64,ZmFrZQ==",
        })

        self.assertEqual(result.status_code, 422)
        self.assertEqual(result.json["data"]["reason"], "face_not_detected")
        with self.app.app_context():
            self.assertEqual(FaceRecord.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
