import sys
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.api import stream_api
from app.core_cv.face_recognizer import FaceRecognizer, SFACE_FEATURE_DIM
from app.core_cv.fall_detector import FallDetector
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

    def test_fall_detector_heuristic(self):
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detector = FallDetector(confirm_frames=1, use_hog=False)

        upright = detector.detect_frame(frame, detections=[{
            "box": [260, 90, 340, 430],
            "className": "person",
            "confidence": 0.9,
        }])
        fallen = detector.detect_frame(frame, detections=[{
            "box": [120, 330, 500, 430],
            "className": "person",
            "confidence": 0.9,
        }])

        self.assertEqual(upright, [])
        self.assertEqual(len(fallen), 1)
        self.assertEqual(fallen[0]["eventType"], "fall")
        self.assertGreaterEqual(fallen[0]["confidence"], 0.58)

    def test_detection_pipeline_creates_fall_alarm(self):
        with self.app.app_context():
            result = DetectionPipeline().process_frame("cam-1", {
                "detections": [{
                    "box": [120, 330, 500, 430],
                    "className": "person",
                    "confidence": 0.91,
                    "severity": "high",
                }],
            })

        self.assertEqual(len(result["alarms"]), 1)
        self.assertEqual(result["alarms"][0]["eventType"], "fall")
        self.assertEqual(result["alarms"][0]["severity"], "high")

    def test_live_stream_draws_and_reports_fire_detection(self):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        fire = {
            "box": [40, 50, 180, 190],
            "className": "fire",
            "eventType": "fire",
            "confidence": 0.91,
            "severity": "critical",
        }
        detector = Mock()
        detector.detect_frame.return_value = [fire]

        with self.app.app_context(), \
                patch.object(stream_api, "_get_fire_detector", return_value=detector), \
                patch.object(stream_api, "_known_faces", return_value=[]), \
                patch.object(stream_api._face_recognizer, "recognize_frame", return_value=[]), \
                patch.object(stream_api._fall_detector, "detect_frame", return_value=[]), \
                patch.object(stream_api, "_maybe_create_fire_alarm") as create_alarm:
            annotated = stream_api._annotate_frame(frame, "cam-1")

        detector.detect_frame.assert_called_once()
        create_alarm.assert_called_once_with(fire, "cam-1")
        self.assertGreater(int(annotated.sum()), 0)

    def test_face_and_liveness_helpers(self):
        recognizer = FaceRecognizer()
        feature = recognizer.extract_feature("data:image/jpeg;base64,ZmFrZQ==")
        self.assertIsInstance(feature, list)
        self.assertEqual(len(feature), SFACE_FEATURE_DIM)
        self.assertEqual(len(recognizer.extract_features("data:image/jpeg;base64,ZmFrZQ==")), 1)
        self.assertTrue(recognizer.compare(feature, feature)["matched"])
        self.assertEqual(recognizer.detect_and_recognize_in_person(None, [0, 0, 1, 1])[2], "Stranger")

        detector = LivenessDetector()
        self.assertEqual(detector.is_live(None), (False, 0.0))
        self.assertTrue(detector.detect({"isLive": True}))

    def test_passive_liveness_rejects_static_image(self):
        detector = LivenessDetector(window_size=12, min_frames=6, static_threshold=0.85)
        frame = np.full((160, 160, 3), 127, dtype=np.uint8)
        result = None
        for _ in range(6):
            result = detector.analyze(frame, [20, 20, 120, 120], "static", model_score=0.9)
        self.assertEqual(result["status"], "spoof")
        self.assertEqual(result["reason"], "static_image")

    def test_passive_liveness_accepts_natural_temporal_variation(self):
        detector = LivenessDetector(window_size=12, min_frames=6, static_threshold=0.4)
        rng = np.random.default_rng(7)
        result = None
        for index in range(6):
            frame = rng.integers(0, 256, (160, 160, 3), dtype=np.uint8)
            frame = np.roll(frame, index * 2, axis=1)
            result = detector.analyze(frame, [20, 20, 120, 120], "live", model_score=0.9)
        self.assertEqual(result["status"], "live")
        self.assertGreater(result["score"], 0.49)

    def test_pretrained_model_score_rejects_spoof(self):
        detector = LivenessDetector(window_size=8, min_frames=5, static_threshold=0.2)
        rng = np.random.default_rng(11)
        result = None
        for _ in range(5):
            frame = rng.integers(0, 256, (160, 160, 3), dtype=np.uint8)
            result = detector.analyze(
                frame,
                [20, 20, 120, 120],
                "model-spoof",
                model_score=0.1,
            )
        self.assertEqual(result["status"], "spoof")
        self.assertEqual(result["reason"], "model_spoof")
        self.assertLess(result["signals"]["modelLiveScore"], detector.model_threshold)

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

    def test_register_face_accumulates_multiple_samples(self):
        first_feature = [1.0] + [0.0] * (SFACE_FEATURE_DIM - 1)
        second_feature = [0.0, 1.0] + [0.0] * (SFACE_FEATURE_DIM - 2)

        first = self.client.post("/api/faces/register", headers=self.headers, json={
            "studentId": "S002",
            "name": "Multi Sample",
            "featureData": first_feature,
        })
        second = self.client.post("/api/faces/register", headers=self.headers, json={
            "studentId": "S002",
            "name": "Multi Sample",
            "featureData": second_feature,
        })

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.json["data"]["sampleCount"], 2)

        with self.app.app_context():
            record = FaceRecord.query.filter_by(student_id="S002").one()
            self.assertEqual(len(record.get_features()), 2)
            recognizer = FaceRecognizer()
            matched, distance = recognizer.match(second_feature, [{
                "id": record.id,
                "name": record.name,
                "features": record.get_features(),
            }])

        self.assertEqual(matched["name"], "Multi Sample")
        self.assertEqual(distance, 0.0)

    def test_face_match_rejects_ambiguous_candidates(self):
        recognizer = FaceRecognizer(threshold=0.9)
        probe = [1.0, 0.0] + [0.0] * (SFACE_FEATURE_DIM - 2)
        close_a = [0.99, 0.10] + [0.0] * (SFACE_FEATURE_DIM - 2)
        close_b = [0.99, -0.10] + [0.0] * (SFACE_FEATURE_DIM - 2)
        matched, distance = recognizer.match(probe, [
            {"id": 1, "name": "A", "feature": close_a},
            {"id": 2, "name": "B", "feature": close_b},
        ])
        self.assertIsNone(matched)
        self.assertIsNotNone(distance)


if __name__ == "__main__":
    unittest.main()
