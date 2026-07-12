"""Passive, challenge-free presentation attack detection helpers.

This module intentionally returns an ``unknown`` result while its temporal
window is warming up.  Callers must never treat unknown as a successful
liveness decision.
"""

from collections import defaultdict, deque
import os
from pathlib import Path

import cv2
import numpy as np


WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
MINIFASNET_MODEL = WEIGHTS_DIR / "minifasnet_v2se.onnx"
MINIFASNET_SHA256 = "fde20585635cae62ed1d41796f76b6f8bc4b92cd91ec1cf0f1bc6485d2d587a9"


class MiniFASNetPredictor:
    """ONNX inference wrapper for the pretrained passive anti-spoof model."""

    def __init__(self, model_path=MINIFASNET_MODEL):
        self.model_path = Path(model_path)
        self.session = None
        self.input_name = None
        self.error = None
        try:
            import onnxruntime as ort

            self.session = ort.InferenceSession(
                str(self.model_path),
                providers=["CPUExecutionProvider"],
            )
            self.input_name = self.session.get_inputs()[0].name
        except Exception as exc:  # dependency/model errors are exposed in results
            self.error = str(exc)

    @property
    def available(self):
        return self.session is not None

    def predict(self, frame, face_box):
        if not self.available or frame is None or not face_box:
            return None
        crop = self._expanded_square_crop(frame, face_box, 1.5)
        if crop is None or crop.size == 0:
            return None
        # The upstream model was trained with RGB input, letterbox reflection
        # padding, and [0, 1] normalization.
        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        tensor = self._preprocess(rgb, 128)[None, ...]
        logits = self.session.run(None, {self.input_name: tensor})[0][0]
        if len(logits) != 2:
            raise ValueError(f"Unexpected MiniFASNet output shape: {logits.shape}")
        logit_diff = float(logits[0] - logits[1])  # upstream: [real, spoof]
        real_probability = float(1.0 / (1.0 + np.exp(-np.clip(logit_diff, -30, 30))))
        return {
            "realProbability": real_probability,
            "realLogit": float(logits[0]),
            "spoofLogit": float(logits[1]),
        }

    @staticmethod
    def _preprocess(image, size):
        height, width = image.shape[:2]
        ratio = float(size) / max(height, width)
        resized_width, resized_height = int(width * ratio), int(height * ratio)
        interpolation = cv2.INTER_LANCZOS4 if ratio > 1.0 else cv2.INTER_AREA
        image = cv2.resize(image, (resized_width, resized_height), interpolation=interpolation)
        delta_w, delta_h = size - resized_width, size - resized_height
        image = cv2.copyMakeBorder(
            image,
            delta_h // 2,
            delta_h - delta_h // 2,
            delta_w // 2,
            delta_w - delta_w // 2,
            cv2.BORDER_REFLECT_101,
        )
        return image.transpose(2, 0, 1).astype(np.float32) / 255.0

    @staticmethod
    def _expanded_square_crop(frame, box, scale):
        frame_height, frame_width = frame.shape[:2]
        x, y, width, height = [int(value) for value in box]
        side = max(width, height) * scale
        center_x, center_y = x + width / 2.0, y + height / 2.0
        left, top = int(center_x - side / 2), int(center_y - side / 2)
        right, bottom = int(left + side), int(top + side)
        source_left, source_top = max(0, left), max(0, top)
        source_right, source_bottom = min(frame_width, right), min(frame_height, bottom)
        if source_right <= source_left or source_bottom <= source_top:
            return None
        crop = frame[source_top:source_bottom, source_left:source_right]
        return cv2.copyMakeBorder(
            crop,
            max(0, -top),
            max(0, bottom - frame_height),
            max(0, -left),
            max(0, right - frame_width),
            cv2.BORDER_REFLECT_101,
        )


class LivenessDetector:
    """Detect common printed-photo and screen-replay attacks from RGB frames.

    The detector is deliberately conservative.  It combines temporal motion,
    duplicate-frame, frequency-domain moire and rectangular-screen-edge cues.
    A production PAD ONNX model can later be fused through ``model_score``.
    """

    def __init__(self, window_size=None, min_frames=None, static_threshold=None, predictor=None):
        self.window_size = int(window_size or os.getenv("LIVENESS_WINDOW_FRAMES", "18"))
        self.min_frames = int(min_frames or os.getenv("LIVENESS_MIN_FRAMES", "10"))
        self.static_threshold = float(
            static_threshold or os.getenv("LIVENESS_STATIC_MOTION_THRESHOLD", "0.85")
        )
        self._history = defaultdict(lambda: deque(maxlen=self.window_size))
        self._model_scores = defaultdict(lambda: deque(maxlen=self.window_size))
        self.predictor = predictor if predictor is not None else MiniFASNetPredictor()
        self.model_threshold = float(os.getenv("LIVENESS_MODEL_THRESHOLD", "0.65"))
        self.model_min_frames = int(os.getenv("LIVENESS_MODEL_MIN_FRAMES", "5"))

    def reset(self, stream_id=None):
        if stream_id is None:
            self._history.clear()
            self._model_scores.clear()
        else:
            self._history.pop(str(stream_id), None)
            self._model_scores.pop(str(stream_id), None)

    def analyze(self, frame, face_box=None, stream_id="default", model_score=None):
        if frame is None or not hasattr(frame, "size") or frame.size == 0:
            return self._result("spoof", 0.0, "empty_frame", 0)

        roi = self._face_context(frame, face_box)
        if roi.size == 0:
            return self._result("unknown", 0.0, "invalid_face_region", 0)

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (128, 128), interpolation=cv2.INTER_AREA)
        gray = cv2.equalizeHist(gray)
        history = self._history[str(stream_id)]
        history.append(gray)

        model_details = None
        if model_score is None and self.predictor is not None:
            try:
                model_details = self.predictor.predict(frame, face_box)
                if model_details is not None:
                    model_score = model_details["realProbability"]
            except Exception as exc:
                self.predictor.error = str(exc)
        scores = self._model_scores[str(stream_id)]
        if model_score is not None:
            scores.append(float(np.clip(model_score, 0.0, 1.0)))

        if self.predictor is not None and not self.predictor.available and model_score is None:
            result = self._result("unknown", 0.0, "model_unavailable", len(history))
            result["modelAvailable"] = False
            result["modelError"] = self.predictor.error
            return result
        if len(history) < self.min_frames or len(scores) < self.model_min_frames:
            result = self._result("unknown", 0.0, "warming_up", len(history))
            result["modelAvailable"] = bool(self.predictor and self.predictor.available)
            return result

        frames = list(history)
        motions = [
            float(np.mean(cv2.absdiff(frames[index - 1], frames[index])))
            for index in range(1, len(frames))
        ]
        mean_motion = float(np.mean(motions))
        moving_ratio = float(np.mean(np.asarray(motions) >= self.static_threshold))
        duplicate_ratio = float(np.mean(np.asarray(motions) < 0.12))
        moire_score = self._moire_score(gray)
        screen_score = self._screen_edge_score(roi)
        model_live_score = float(np.mean(scores))

        reasons = []
        # A held photograph or frozen virtual-camera frame has almost no local
        # pixel evolution over a multi-frame window.
        if mean_motion < self.static_threshold or moving_ratio < 0.35:
            reasons.append("static_image")
        if duplicate_ratio > 0.45:
            reasons.append("repeated_frames")
        # Screen replay commonly exposes both a regular pixel lattice and a
        # strong rectangular display boundary.  Require both to reduce false
        # positives from glasses, windows and patterned clothing.
        if moire_score > 0.58 and screen_score > 0.45:
            reasons.append("screen_replay")
        if model_live_score < self.model_threshold:
            reasons.append("model_spoof")

        temporal_score = np.clip((mean_motion - 0.25) / 2.75, 0.0, 1.0)
        score = float(
            0.58 * temporal_score
            + 0.22 * (1.0 - duplicate_ratio)
            + 0.12 * (1.0 - moire_score)
            + 0.08 * (1.0 - screen_score)
        )
        score = float(0.35 * score + 0.65 * model_live_score)

        status = "spoof" if reasons else "live"
        if status == "spoof":
            score = min(score, 0.49)
        return {
            **self._result(status, score, reasons[0] if reasons else "passive_live", len(history)),
            "signals": {
                "meanMotion": round(mean_motion, 3),
                "movingRatio": round(moving_ratio, 3),
                "duplicateRatio": round(duplicate_ratio, 3),
                "moireScore": round(moire_score, 3),
                "screenScore": round(screen_score, 3),
                "modelLiveScore": round(model_live_score, 3),
            },
            "modelAvailable": bool(self.predictor and self.predictor.available),
            "model": model_details,
        }

    def is_live(self, frame, face_box=None, stream_id="default"):
        result = self.analyze(frame, face_box=face_box, stream_id=stream_id)
        return result["status"] == "live", result["score"]

    def detect(self, frame):
        # Retain compatibility for existing synthetic pipeline inputs.
        if isinstance(frame, dict) and "isLive" in frame:
            return bool(frame["isLive"])
        return self.is_live(frame)[0]

    @staticmethod
    def _result(status, score, reason, frame_count):
        return {
            "status": status,
            "isLive": status == "live",
            "score": round(float(score), 3),
            "reason": reason,
            "frameCount": frame_count,
        }

    @staticmethod
    def _face_context(frame, box):
        if not box:
            return frame
        height, width = frame.shape[:2]
        x, y, face_width, face_height = [int(value) for value in box]
        pad_x, pad_y = int(face_width * 0.35), int(face_height * 0.35)
        left, top = max(0, x - pad_x), max(0, y - pad_y)
        right = min(width, x + face_width + pad_x)
        bottom = min(height, y + face_height + pad_y)
        return frame[top:bottom, left:right]

    @staticmethod
    def _moire_score(gray):
        spectrum = np.log1p(np.abs(np.fft.fftshift(np.fft.fft2(gray))))
        height, width = spectrum.shape
        spectrum[height // 2 - 5:height // 2 + 6, width // 2 - 5:width // 2 + 6] = 0
        threshold = float(np.mean(spectrum) + 2.6 * np.std(spectrum))
        peaks = float(np.mean(spectrum > threshold))
        return float(np.clip(peaks / 0.018, 0.0, 1.0))

    @staticmethod
    def _screen_edge_score(roi):
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 70, 180)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        area = float(max(1, gray.shape[0] * gray.shape[1]))
        best = 0.0
        for contour in contours:
            perimeter = cv2.arcLength(contour, True)
            polygon = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
            if len(polygon) == 4 and cv2.isContourConvex(polygon):
                ratio = cv2.contourArea(polygon) / area
                if 0.18 <= ratio <= 0.95:
                    best = max(best, min(1.0, ratio / 0.65))
        return float(best)
