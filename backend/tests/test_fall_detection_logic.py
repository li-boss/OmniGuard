import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np

from core_cv.fall_detector import FallDetector
from core_cv.pipeline import CameraPipeline


def _landmark(x, y, visibility=1.0):
    return SimpleNamespace(x=x, y=y, z=0.0, visibility=visibility)


def _standing_landmarks():
    landmarks = [_landmark(0.5, 0.5) for _ in range(33)]
    landmarks[11] = _landmark(0.4, 0.2)
    landmarks[12] = _landmark(0.6, 0.2)
    landmarks[23] = _landmark(0.42, 0.5)
    landmarks[24] = _landmark(0.58, 0.5)
    landmarks[25] = _landmark(0.43, 0.7)
    landmarks[26] = _landmark(0.57, 0.7)
    landmarks[27] = _landmark(0.44, 0.95)
    landmarks[28] = _landmark(0.56, 0.95)
    return landmarks


class FallDetectorLogicTests(unittest.TestCase):
    def setUp(self):
        self.detector = FallDetector.__new__(FallDetector)
        self.detector.angle_threshold = 30
        self.detector.hip_height_threshold = 0.5
        self.detector.confidence_threshold = 0.5
        self.detector.timestamp = 0

    def test_standing_pose_does_not_trigger(self):
        detected, confidence, details = self.detector._analyze_pose(_standing_landmarks())

        self.assertFalse(detected)
        self.assertEqual(confidence, 0.0)
        self.assertLess(len(details["fall_indicators"]), 2)

    def test_two_indicators_are_required(self):
        landmarks = _standing_landmarks()
        landmarks[11] = _landmark(0.2, 0.4)
        landmarks[12] = _landmark(0.4, 0.4)

        detected, confidence, details = self.detector._analyze_pose(landmarks)

        self.assertTrue(detected)
        self.assertGreaterEqual(len(details["fall_indicators"]), 2)
        self.assertGreater(confidence, 0.0)

    def test_six_visible_points_are_enough_for_analysis(self):
        landmarks = _standing_landmarks()
        landmarks[26].visibility = 0.2
        landmarks[28].visibility = 0.2

        detected, _, details = self.detector._analyze_pose(landmarks)

        self.assertFalse(detected)
        self.assertEqual(details["visible_points"], 6)
        self.assertFalse(details["complete_body"])

    def test_bent_low_pose_without_tilt_does_not_trigger(self):
        landmarks = _standing_landmarks()
        landmarks[23] = _landmark(0.42, 0.55)
        landmarks[24] = _landmark(0.58, 0.55)
        landmarks[25] = _landmark(0.35, 0.67)
        landmarks[26] = _landmark(0.65, 0.67)
        landmarks[27] = _landmark(0.45, 0.78)
        landmarks[28] = _landmark(0.55, 0.78)

        detected, _, details = self.detector._analyze_pose(landmarks)

        self.assertFalse(detected)
        self.assertNotIn("body_tilt", details["fall_indicators"])

    def test_xyxy_bbox_produces_exact_pose_crop(self):
        pose = MagicMock()
        pose.detect.return_value = SimpleNamespace(pose_landmarks=[])
        self.detector.pose = pose
        frame = np.zeros((100, 120, 3), dtype=np.uint8)

        self.detector.detect(frame, [10, 20, 50, 70])

        mp_image = pose.detect.call_args.args[0]
        self.assertEqual((mp_image.height, mp_image.width), (50, 40))


class FallConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.pipeline = CameraPipeline.__new__(CameraPipeline)
        self.pipeline.fall_confirmation_history = {}
        self.pipeline.fall_confirmation_window = 5
        self.pipeline.fall_confirmation_required = 3

    def test_requires_three_positive_results(self):
        positive = {"fall_detected": True}

        self.assertFalse(self.pipeline._confirm_fall(7, positive))
        self.assertFalse(self.pipeline._confirm_fall(7, positive))
        self.assertTrue(self.pipeline._confirm_fall(7, positive))

    def test_one_negative_result_does_not_discard_positive_history(self):
        positive = {"fall_detected": True}

        self.assertFalse(self.pipeline._confirm_fall(7, positive))
        self.assertFalse(self.pipeline._confirm_fall(7, {"fall_detected": False}))
        self.assertFalse(self.pipeline._confirm_fall(7, positive))
        self.assertTrue(self.pipeline._confirm_fall(7, positive))

    def test_none_result_does_not_confirm(self):
        self.assertFalse(self.pipeline._confirm_fall(7, None))
        self.assertEqual(self.pipeline.fall_confirmation_history[7], [False])


if __name__ == "__main__":
    unittest.main()
