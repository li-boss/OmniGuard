import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from flask import Flask

from services.audio_event_detector import (
    AcousticAnomalyDetector,
    AudioEventDetector,
    DetectionGate,
    merge_yamnet_class,
)


class AudioClassMergeTests(unittest.TestCase):
    def test_explosion_classes_are_merged(self):
        for class_name in (
            "Explosion",
            "Boom",
            "Fireworks",
            "Firecracker",
            "Burst, pop",
            "Eruption",
            "Gunshot, gunfire",
            "Machine gun",
            "Fusillade",
            "Artillery fire",
            "Cap gun",
        ):
            self.assertEqual(merge_yamnet_class(class_name), "explosion")

    def test_glass_break_classes_are_merged(self):
        for class_name in (
            "Glass",
            "Shatter",
            "Breaking",
            "Smash, crash",
            "Crack",
            "Chink, clink",
        ):
            self.assertEqual(merge_yamnet_class(class_name), "glass_break")

    def test_unrelated_class_is_ignored(self):
        self.assertIsNone(merge_yamnet_class("Speech"))
        self.assertIsNone(merge_yamnet_class("Crackle"))


class DetectionGateTests(unittest.TestCase):
    def setUp(self):
        self.gate = DetectionGate(
            {"explosion": 0.6, "glass_break": 0.4},
            confirmation_count=2,
            cooldown_seconds=3.0,
        )

    def test_uses_category_specific_thresholds(self):
        self.assertFalse(self.gate.evaluate("explosion", 0.5, now=0.0))
        self.assertFalse(self.gate.evaluate("glass_break", 0.5, now=0.1))
        self.assertTrue(self.gate.evaluate("glass_break", 0.5, now=0.2))

    def test_requires_two_consecutive_detections(self):
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=0.0))
        self.assertTrue(self.gate.evaluate("explosion", 0.8, now=0.5))

    def test_below_threshold_resets_confirmation(self):
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=0.0))
        self.assertFalse(self.gate.evaluate("explosion", 0.2, now=0.2))
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=0.4))

    def test_cooldown_suppresses_duplicate_alarm(self):
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=0.0))
        self.assertTrue(self.gate.evaluate("explosion", 0.8, now=0.1))
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=1.0))
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=1.1))
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=3.2))
        self.assertTrue(self.gate.evaluate("explosion", 0.8, now=3.3))

    def test_confirmation_can_be_reset_between_sessions(self):
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=0.0))
        self.gate.reset_confirmation()
        self.assertFalse(self.gate.evaluate("explosion", 0.8, now=0.5))


class YamnetOutputTests(unittest.TestCase):
    def test_grouped_score_and_1024_embedding_interface(self):
        app = Flask("audio_test", root_path=str(__import__("pathlib").Path(__file__).parents[1]))
        detector = AudioEventDetector(app)
        detector.class_names = ["Speech", "Explosion", "Glass", "Boom"]

        def tensor(values):
            return SimpleNamespace(numpy=lambda: np.asarray(values, dtype=np.float32))

        detector.model = lambda waveform: (
            tensor([[0.1, 0.8, 0.2, 0.4], [0.1, 0.7, 0.3, 0.5]]),
            tensor(np.ones((2, 1024), dtype=np.float32)),
            tensor(np.zeros((2, 64), dtype=np.float32)),
        )

        result = detector.analyze_waveform(np.zeros(15360, dtype=np.float32))
        embedding = detector.extract_embeddings(np.zeros(15360, dtype=np.float32))

        self.assertEqual(result["category"], "explosion")
        self.assertEqual(result["matched_raw_class"], "Explosion")
        self.assertAlmostEqual(result["confidence"], 0.8, places=5)
        self.assertAlmostEqual(result["explosion_score"], 0.8, places=5)
        self.assertAlmostEqual(result["glass_break_score"], 0.3, places=5)
        self.assertEqual(
            [prediction["class_name"] for prediction in result["top_predictions"]],
            ["Explosion", "Boom", "Glass", "Speech"],
        )
        self.assertAlmostEqual(result["top_predictions"][0]["confidence"], 0.75, places=5)
        self.assertEqual(embedding.shape, (1024,))

    def test_target_below_threshold_is_displayed_as_other(self):
        app = Flask("audio_low_score_test", root_path=str(__import__("pathlib").Path(__file__).parents[1]))
        detector = AudioEventDetector(app)
        detector.gate.thresholds = {"explosion": 0.45, "glass_break": 0.35}
        detector.class_names = ["Speech", "Explosion", "Glass"]

        def tensor(values):
            return SimpleNamespace(numpy=lambda: np.asarray(values, dtype=np.float32))

        detector.model = lambda waveform: (
            tensor([[0.9, 0.01, 0.02]]),
            tensor(np.ones((1, 1024), dtype=np.float32)),
            tensor(np.zeros((1, 64), dtype=np.float32)),
        )

        result = detector.analyze_waveform(np.zeros(15360, dtype=np.float32))

        self.assertIsNone(result["category"])
        self.assertEqual(result["display_name"], "其他声音")
        self.assertAlmostEqual(result["confidence"], 0.02, places=5)
        self.assertEqual(result["matched_raw_class"], "Glass")


class TriggeredResultDisplayTests(unittest.TestCase):
    def setUp(self):
        app = Flask("audio_display_test", root_path=str(__import__("pathlib").Path(__file__).parents[1]))
        self.detector = AudioEventDetector(app)
        self.detector.display_hold_seconds = 5.0
        self.triggered = {
            "category": "glass_break",
            "display_name": "玻璃破碎声",
            "confidence": 0.83,
            "triggered": True,
        }
        self.current = {
            "category": None,
            "display_name": "其他声音",
            "confidence": 1.0,
            "triggered": False,
        }
        self.detector._last_triggered_result = self.triggered
        self.detector._last_triggered_monotonic = 100.0
        self.detector._last_result = self.current

    @patch("services.audio_event_detector.time.monotonic", return_value=104.9)
    def test_triggered_result_is_displayed_during_hold_period(self, _monotonic):
        status = self.detector.status()

        self.assertEqual(status["last_result"], self.triggered)
        self.assertEqual(status["last_triggered_result"], self.triggered)

    @patch("services.audio_event_detector.time.monotonic", return_value=105.0)
    def test_live_result_returns_after_hold_period(self, _monotonic):
        self.assertEqual(self.detector.status()["last_result"], self.current)


class InputResamplingTests(unittest.TestCase):
    def setUp(self):
        app = Flask("audio_resampling_test", root_path=str(__import__("pathlib").Path(__file__).parents[1]))
        self.detector = AudioEventDetector(app)

    def test_native_48k_audio_is_resampled_to_yamnet_16k(self):
        self.detector.input_sample_rate = 48000
        chunk = np.ones(4800, dtype=np.float32)

        result = self.detector._resample_for_model(chunk)

        self.assertEqual(result.dtype, np.float32)
        self.assertEqual(result.shape, (1600,))

    def test_16k_audio_does_not_require_resampling(self):
        self.detector.input_sample_rate = 16000
        chunk = np.ones(1600, dtype=np.float32)

        result = self.detector._resample_for_model(chunk)

        self.assertIs(result, chunk)

    def test_pending_chunks_are_coalesced_before_inference(self):
        first = np.full(2, 1.0, dtype=np.float32)
        self.detector._audio_queue.put(np.full(2, 2.0, dtype=np.float32))
        self.detector._audio_queue.put(np.full(2, 3.0, dtype=np.float32))

        result = self.detector._coalesce_pending_chunks(first)

        np.testing.assert_array_equal(result, np.asarray([1, 1, 2, 2, 3, 3], dtype=np.float32))
        self.assertEqual(self.detector._audio_queue.qsize(), 0)
        self.assertEqual(self.detector._coalesced_chunks, 2)


class RemoteAcousticModuleTests(unittest.TestCase):
    def test_impulsive_audio_is_reported_as_candidate_only(self):
        detector = AcousticAnomalyDetector()
        samples = np.zeros(16000, dtype=np.float32)
        samples[8000] = 1.0

        candidates = detector.analyze(samples, 16000)

        self.assertIn("impact_candidate", [candidate["label"] for candidate in candidates])

    def test_quiet_non_silent_audio_is_normalized_for_yamnet(self):
        samples = np.full(16000, 0.01, dtype=np.float32)

        normalized = AudioEventDetector._normalize_for_inference(samples)

        self.assertAlmostEqual(float(np.sqrt(np.mean(np.square(normalized)))), 0.08, places=4)

    def test_silence_is_not_amplified(self):
        samples = np.zeros(16000, dtype=np.float32)

        normalized = AudioEventDetector._normalize_for_inference(samples)

        self.assertTrue(np.array_equal(normalized, samples))


if __name__ == "__main__":
    unittest.main()
