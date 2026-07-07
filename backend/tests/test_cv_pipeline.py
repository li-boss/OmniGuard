import os
import sys
import unittest
from unittest.mock import MagicMock, patch
import numpy as np
import cv2
import time

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from models import db, AlertZone, RegisteredFace
from core_cv.model_loader import ModelLoader
from core_cv.stream_manager import StreamManager
from core_cv.yolo_detector import YoloDetector
from core_cv.face_recognizer import FaceRecognizer
from core_cv.rule_engine import RuleEngine
from core_cv.pipeline import CameraPipelineManager, CameraPipeline, iou, SimpleTracker


class TestCVPipelineComponents(unittest.TestCase):

    def test_iou_calculation(self):
        box1 = [0, 0, 10, 10]
        box2 = [5, 5, 15, 15]
        # Intersection: [5, 5, 10, 10] -> area 25
        # Union: 100 + 100 - 25 = 175
        # IoU = 25/175 = 0.142857
        self.assertAlmostEqual(iou(box1, box2), 25.0/175.0, places=5)
        
        # No overlap
        box3 = [20, 20, 30, 30]
        self.assertEqual(iou(box1, box3), 0.0)

    def test_simple_tracker(self):
        tracker = SimpleTracker(max_lost_seconds=1.0)
        
        # Initial detections
        detections = [[10, 10, 50, 50], [100, 100, 150, 150]]
        tracks = tracker.update(detections)
        self.assertEqual(len(tracks), 2)
        self.assertIn(1, tracks)
        self.assertIn(2, tracks)
        
        # Move boxes slightly
        moved_detections = [[12, 12, 52, 52], [101, 101, 151, 151]]
        tracks = tracker.update(moved_detections)
        self.assertEqual(len(tracks), 2)
        self.assertIn(1, tracks)
        self.assertIn(2, tracks)
        
        # Sleep to let track 2 age slightly, but not expire yet
        import time
        time.sleep(0.6)
        
        # One box disappears, check if it's kept (within 1 second)
        one_detection = [[12, 12, 52, 52]]
        tracks = tracker.update(one_detection)
        self.assertEqual(len(tracks), 2)
        
        # Sleep again. Total age of track 2 will be 0.6 + 0.6 = 1.2s (> 1.0s),
        # but track 1 age will only be 0.6s (< 1.0s).
        time.sleep(0.6)
        tracks = tracker.update(one_detection)
        self.assertEqual(len(tracks), 1)
        self.assertIn(1, tracks)
        self.assertNotIn(2, tracks)

    def test_rule_engine_point_in_polygon(self):
        engine = RuleEngine()
        polygon = [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
        
        point_inside = (0.5, 0.5)
        point_outside = (1.5, 0.5)
        
        self.assertTrue(engine.point_in_polygon(point_inside, polygon))
        self.assertFalse(engine.point_in_polygon(point_outside, polygon))

    def test_rule_engine_evaluate_stay(self):
        engine = RuleEngine()
        zone = {
            "id": 1,
            "name": "Test Zone",
            "polygon": [{"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}],
            "stay_seconds": 1
        }
        
        # Object inside the zone - first time
        box_in = [0.1, 0.1, 0.3, 0.3]  # bottom center is (0.2, 0.3) -> inside
        should_trigger, duration = engine.evaluate_stay(1, box_in, zone)
        self.assertFalse(should_trigger)
        self.assertEqual(duration, 0.0)
        
        # Immediate check - duration < 1s
        should_trigger, duration = engine.evaluate_stay(1, box_in, zone)
        self.assertFalse(should_trigger)
        
        # Sleep to exceed stay_seconds
        import time
        time.sleep(1.1)
        
        # Should trigger alarm
        should_trigger, duration = engine.evaluate_stay(1, box_in, zone)
        self.assertTrue(should_trigger)
        self.assertGreaterEqual(duration, 1.0)
        
        # Subsequent checks should suppress alarm
        should_trigger, duration = engine.evaluate_stay(1, box_in, zone)
        self.assertFalse(should_trigger)
        
        # Object leaves zone
        box_out = [1.2, 1.2, 1.4, 1.4]
        should_trigger, duration = engine.evaluate_stay(1, box_out, zone)
        self.assertFalse(should_trigger)
        
        # Re-enters - should reset and start over
        should_trigger, duration = engine.evaluate_stay(1, box_in, zone)
        self.assertFalse(should_trigger)

    @patch('cv2.VideoCapture')
    def test_stream_manager_grab_retrieve(self, mock_vc_class):
        mock_vc = MagicMock()
        mock_vc.isOpened.return_value = True
        # grab returns True then False (simulates 1 frame in buffer)
        mock_vc.grab.side_effect = [True, False]
        mock_vc.retrieve.return_value = (True, np.zeros((100, 100, 3), dtype=np.uint8))
        mock_vc_class.return_value = mock_vc
        
        stream = StreamManager("rtsp://test_stream", frame_skip=1)
        stream.connect()
        
        frame = stream.get_latest_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (100, 100, 3))


class TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "test"
    JWT_SECRET_KEY = "test"
    RTMP_URL = ""
    DINGTALK_WEBHOOK = ""


class TestFlaskIntegration(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        
        with self.app.app_context():
            db.create_all()
            
    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        # Reset CameraPipelineManager singleton state
        manager = CameraPipelineManager()
        with manager._lock:
            manager.pipelines.clear()
            manager.dirty_cameras.clear()

    def test_rules_api_marks_dirty_and_status(self):
        # Verify initial cameras status is empty
        response = self.client.get("/api/cameras/status")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])
        
        # Add a new alert zone
        zone_payload = {
            "camera_id": "cam_01",
            "name": "Entrance Fence",
            "polygon": [{"x": 0.1, "y": 0.1}, {"x": 0.5, "y": 0.1}, {"x": 0.5, "y": 0.5}, {"x": 0.1, "y": 0.5}],
            "stay_seconds": 10,
            "enabled": True,
            "distance_threshold": 0.0
        }
        
        response = self.client.post("/api/zones", json=zone_payload)
        self.assertEqual(response.status_code, 201)
        
        # Verify camera is marked dirty in pipeline manager
        manager = CameraPipelineManager()
        self.assertIn("cam_01", manager.dirty_cameras)


class TestFaceRecognizer(unittest.TestCase):
    def test_extract_feature_invalid_input(self):
        recognizer = FaceRecognizer()
        # Test None input
        self.assertIsNone(recognizer.extract_feature(None))
        # Test empty image
        empty_img = np.zeros((0, 0, 3), dtype=np.uint8)
        self.assertIsNone(recognizer.extract_feature(empty_img))
        
    def test_compare_boundary(self):
        recognizer = FaceRecognizer(threshold=0.6)
        f1 = np.ones(128, dtype=np.float32) / np.linalg.norm(np.ones(128, dtype=np.float32))
        
        # Test exact match
        res = recognizer.compare(f1, f1)
        self.assertTrue(res["matched"])
        self.assertAlmostEqual(res["distance"], 0.0)
        
        # Test boundary below threshold
        f2 = f1.copy()
        f2[0] += 0.4  # will make distance around 0.4
        f2 = f2 / np.linalg.norm(f2)
        res = recognizer.compare(f1, f2)
        self.assertLess(res["distance"], 0.6)
        self.assertTrue(res["matched"])
        
        # Test boundary above threshold
        f3 = -f1.copy() # distance will be 2.0 (maximal)
        res = recognizer.compare(f1, f3)
        self.assertGreater(res["distance"], 0.6)
        self.assertFalse(res["matched"])

    def test_empty_known_faces(self):
        recognizer = FaceRecognizer()
        frame = np.zeros((300, 300, 3), dtype=np.uint8)
        box = [50, 50, 150, 150]
        
        # With empty known_faces, detect_and_recognize_in_person should not crash and return Stranger
        found, face_box, name, user_id, dist = recognizer.detect_and_recognize_in_person(frame, box)
        self.assertFalse(found)
        self.assertEqual(name, "Stranger")
        self.assertIsNone(user_id)
        self.assertEqual(dist, 1.0)

    def test_l2_normalization(self):
        recognizer = FaceRecognizer()
        # Test extract_feature returns L2 normalized vector
        dummy_face = np.random.randint(0, 255, (112, 112, 3), dtype=np.uint8)
        feat = recognizer.extract_feature(dummy_face)
        if feat is not None:
            norm = np.linalg.norm(feat)
            self.assertAlmostEqual(norm, 1.0, places=5)

    def test_concurrent_reload_and_match(self):
        recognizer = FaceRecognizer()
        recognizer.known_faces = {
            i: {"name": f"User_{i}", "feature": np.random.randn(128).astype(np.float32)}
            for i in range(100)
        }
        
        stop_threads = False
        
        def writer_thread():
            while not stop_threads:
                with recognizer._lock:
                    new_faces = {
                        i: {"name": f"User_{i}_new", "feature": np.random.randn(128).astype(np.float32)}
                        for i in range(100)
                    }
                    recognizer.known_faces = new_faces
                time.sleep(0.001)

        def reader_thread():
            while not stop_threads:
                feat = np.random.randn(128).astype(np.float32)
                feat = feat / np.linalg.norm(feat)
                with recognizer._lock:
                    for uid, info in recognizer.known_faces.items():
                        dist = np.linalg.norm(feat - info["feature"])
                time.sleep(0.001)

        import threading
        t_write = threading.Thread(target=writer_thread)
        t_read = threading.Thread(target=reader_thread)
        
        t_write.start()
        t_read.start()
        
        time.sleep(0.5)
        stop_threads = True
        t_write.join()
        t_read.join()


class TestCameraPipelineE2E(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Add mock zone
        self.zone = AlertZone(
            id=100,
            camera_id="cam_e2e_01",
            name="E2E Danger Zone",
            polygon=[{"x": 0.0, "y": 0.0}, {"x": 0.5, "y": 0.0}, {"x": 0.5, "y": 0.5}, {"x": 0.0, "y": 0.5}],
            stay_seconds=3,
            enabled=True,
            distance_threshold=0.0
        )
        db.session.add(self.zone)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        
        # Reset CameraPipelineManager singleton state
        manager = CameraPipelineManager()
        with manager._lock:
            manager.pipelines.clear()
            manager.dirty_cameras.clear()

    @patch('core_cv.pipeline.StreamManager')
    @patch('core_cv.pipeline.YoloDetector')
    @patch('core_cv.pipeline.FaceRecognizer')
    @patch('services.ws_handler.emit_alarm')
    def test_pipeline_e2e_alarm_trigger_and_db_write(self, mock_emit_alarm, mock_face_rec_cls, mock_yolo_cls, mock_stream_cls):
        # 1. Setup Mocks
        # Mock StreamManager to return a dummy frame
        mock_stream = MagicMock()
        mock_stream.get_latest_frame.return_value = np.zeros((480, 640, 3), dtype=np.uint8)
        mock_stream_cls.return_value = mock_stream
        
        # Mock YoloDetector to return one person in the zone
        mock_yolo = MagicMock()
        mock_yolo.detect.return_value = [{"box": [100, 100, 200, 200], "box_norm": [0.15, 0.2, 0.3, 0.4]}]
        mock_yolo_cls.return_value = mock_yolo
        
        # Mock FaceRecognizer to find "Bob"
        mock_face_rec = MagicMock()
        mock_face_rec.detect_and_recognize_in_person.return_value = (True, [0.16, 0.22, 0.2, 0.3], "Bob", 42, 0.15)
        mock_face_rec_cls.return_value = mock_face_rec
        
        # 2. Instantiate pipeline
        manager = CameraPipelineManager(self.app)
        # Force initialize and reload dirty pipelines
        manager.dirty_cameras.add("cam_e2e_01")
        manager.reload_dirty_pipelines()
        
        pipeline = manager.pipelines.get("cam_e2e_01")
        self.assertIsNotNone(pipeline)
        pipeline.tracker.max_lost_seconds = 10.0
        
        # Override detectors/managers inside pipeline with our mocks
        pipeline.stream_manager = mock_stream
        pipeline.yolo_detector = mock_yolo
        pipeline.face_recognizer = mock_face_rec
        
        # 3. Simulate process_frame at t = 0 (enters zone)
        t_start = 1700000000.0
        with patch('time.time', return_value=t_start):
            pipeline.process_frame()
            
        # Verify no alarms in queue yet (since duration = 0 < stay_seconds=3)
        from core_cv.pipeline import alarm_queue
        self.assertTrue(alarm_queue.empty())
        
        # 4. Simulate process_frame at t = 5 (duration = 5 > stay_seconds=3)
        with patch('time.time', return_value=t_start + 5.0):
            pipeline.process_frame()
            
        # Verify alarm is added to the queue
        self.assertFalse(alarm_queue.empty())
        alarm_item = alarm_queue.get()
        self.assertEqual(alarm_item["camera_id"], "cam_e2e_01")
        self.assertEqual(alarm_item["name"], "Bob")
        self.assertEqual(alarm_item["alarm_type"], "electronic_fence")
        
        # 5. Process the queue item using AlarmWorker
        # Mock cv2.imwrite to avoid creating files on disk
        from core_cv.pipeline import AlarmWorker
        worker = AlarmWorker(self.app)
        with patch('cv2.imwrite') as mock_imwrite:
            worker.save_and_broadcast_alarm(alarm_item)
            mock_imwrite.assert_called_once()
            
        # 6. Verify AlarmEvent is persisted to SQLite db
        from models.alarm import AlarmEvent
        events = AlarmEvent.query.all()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].camera_id, "cam_e2e_01")
        self.assertEqual(events[0].alarm_type, "electronic_fence")
        self.assertEqual(events[0].level, "medium")
        
        # 7. Verify WebSocket broadcast was emitted
        mock_emit_alarm.assert_called_once()
        emitted_payload = mock_emit_alarm.call_args[0][0]
        self.assertEqual(emitted_payload["id"], events[0].id)
        self.assertEqual(emitted_payload["name"], "Bob")


if __name__ == "__main__":
    unittest.main()
