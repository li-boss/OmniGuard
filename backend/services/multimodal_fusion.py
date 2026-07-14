"""Time-windowed audio, emotion and electronic-fence risk fusion."""

from __future__ import annotations

import csv
import logging
import math
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict

import numpy as np


logger = logging.getLogger(__name__)


DISTRESS_AUDIO = {
    "fight": 1.0,
    "fighting": 1.0,
    "scream": 1.0,
    "screaming": 1.0,
    "help": 1.0,
    "cry_for_help": 1.0,
    "glass_breaking": 0.95,
    "gunshot": 1.0,
    "explosion": 1.0,
    "shout": 0.75,
    "yell": 0.75,
    "argument": 0.8,
    "争吵": 0.8,
    "打架": 1.0,
    "尖叫": 1.0,
    "呼救": 1.0,
}

RISK_EMOTIONS = {
    "angry": 1.0,
    "anger": 1.0,
    "fear": 0.85,
    "distress": 1.0,
    "愤怒": 1.0,
    "恐惧": 0.85,
}


# YAMNet outputs AudioSet display names. Only safety-relevant classes are
# forwarded; generic speech/conversation is excluded to reduce nuisance alarms.
YAMNET_RISK_LABELS = {
    "shout": ("shout", 0.55),
    "yell": ("yell", 0.55),
    "children shouting": ("shout", 0.60),
    "screaming": ("screaming", 0.45),
    "crying, sobbing": ("cry_for_help", 0.65),
    "glass": ("glass_breaking", 0.20),
    "shatter": ("glass_breaking", 0.18),
    "gunshot, gunfire": ("gunshot", 0.15),
    "machine gun": ("gunshot", 0.20),
    "fusillade": ("gunshot", 0.20),
    "artillery fire": ("gunshot", 0.20),
    "cap gun": ("gunshot", 0.18),
    "firecracker": ("gunshot", 0.18),
    "explosion": ("explosion", 0.18),
    "boom": ("explosion", 0.18),
}

# Once YAMNet (or another semantic classifier posting the same normalized
# labels) has crossed its detection threshold, these safety events should
# create an alarm without requiring a second modality. Candidate-only labels
# from the lightweight detector are deliberately excluded.
IMMEDIATE_AUDIO_ALARM_THRESHOLDS = {
    "fight": 0.45,
    "fighting": 0.45,
    "scream": 0.45,
    "screaming": 0.45,
    "help": 0.55,
    "cry_for_help": 0.65,
    "glass_breaking": 0.18,
    "gunshot": 0.15,
    "explosion": 0.18,
    "shout": 0.55,
    "yell": 0.55,
    "argument": 0.55,
}


@dataclass(frozen=True)
class FusionDecision:
    triggered: bool
    score: float
    severity: str
    reasons: tuple[str, ...]
    audio_score: float
    emotion_score: float
    in_zone: bool

    def to_dict(self):
        value = asdict(self)
        value["reasons"] = list(self.reasons)
        return value


class AcousticAnomalyDetector:
    """Lightweight acoustic candidate detector for mono PCM.

    It intentionally reports candidates, not semantic labels such as "fight".
    A trained classifier (for example YAMNet) can submit semantic labels to the
    fusion engine through the multimodal API.
    """

    def analyze(self, samples, sample_rate: int) -> list[dict]:
        pcm = np.asarray(samples, dtype=np.float32).reshape(-1)
        if sample_rate < 8000 or pcm.size < sample_rate // 4:
            raise ValueError("at least 250 ms of PCM at 8 kHz or above is required")
        peak = float(np.max(np.abs(pcm)))
        rms = float(np.sqrt(np.mean(np.square(pcm))))
        signs = np.signbit(pcm)
        zcr = float(np.mean(signs[1:] != signs[:-1]))
        crest = peak / max(rms, 1e-6)

        events = []
        # High-energy, high-frequency human vocalisation candidate.
        scream_score = min(1.0, max(0.0, (rms - 0.08) * 4.5 + (zcr - 0.08) * 2.0))
        if peak > 0.35 and scream_score >= 0.35:
            events.append({"label": "acoustic_distress_candidate", "score": round(scream_score, 4)})
        # Short impulsive sounds (impact/glass/gunshot candidate).
        impact_score = min(1.0, max(0.0, (crest - 4.0) / 8.0 + (peak - 0.6)))
        if peak > 0.65 and impact_score >= 0.35:
            events.append({"label": "impact_candidate", "score": round(impact_score, 4)})
        return events


class YamnetAudioClassifier:
    """Lazy adapter for the official TensorFlow Hub YAMNet model."""

    def __init__(self, enabled=None, model_url=None):
        if enabled is None:
            enabled = os.getenv("AUDIO_SEMANTIC_ENABLED", "false").lower() in {"1", "true", "yes"}
        self.enabled = bool(enabled)
        self.model_url = model_url or os.getenv("YAMNET_MODEL_URL", "https://tfhub.dev/google/yamnet/1")
        self._model = None
        self._class_names = None
        self._lock = threading.RLock()
        self._error = None

    def status(self):
        return {
            "enabled": self.enabled,
            "loaded": self._model is not None,
            "model": "YAMNet",
            "model_url": self.model_url,
            "error": self._error,
        }

    def analyze(self, samples, sample_rate: int) -> list[dict]:
        if not self.enabled:
            return []
        try:
            self._ensure_loaded()
            waveform = self._resample(samples, sample_rate, 16000)
            waveform = self._normalize_for_inference(waveform)
            scores, _, _ = self._model(waveform)
            mean_scores = np.asarray(scores.numpy(), dtype=np.float32).mean(axis=0)
            events = []
            for index, score in enumerate(mean_scores):
                raw_label = self._class_names[index]
                mapping = YAMNET_RISK_LABELS.get(raw_label.strip().lower())
                if mapping is None:
                    continue
                label, threshold = mapping
                value = float(score)
                if value >= threshold:
                    events.append({
                        "label": label,
                        "score": round(value, 4),
                        "raw_label": raw_label,
                        "classifier": "yamnet",
                    })
            events.sort(key=lambda item: item["score"], reverse=True)
            self._error = None
            return events[:3]
        except Exception as exc:
            # Optional model failures must preserve lightweight detection.
            self._error = str(exc)
            logger.warning("YAMNet inference unavailable: %s", exc)
            return []

    def _ensure_loaded(self):
        if self._model is not None:
            return
        with self._lock:
            if self._model is not None:
                return
            try:
                import tensorflow as tf
                import tensorflow_hub as hub
            except ImportError as exc:
                raise RuntimeError(
                    "YAMNet dependencies are missing; install backend/requirements-audio.txt"
                ) from exc
            model = hub.load(self.model_url)
            class_map_path = model.class_map_path().numpy()
            if isinstance(class_map_path, bytes):
                class_map_path = class_map_path.decode("utf-8")
            with tf.io.gfile.GFile(class_map_path) as handle:
                self._class_names = [row["display_name"] for row in csv.DictReader(handle)]
            self._model = model

    @staticmethod
    def _resample(samples, source_rate, target_rate):
        pcm = np.asarray(samples, dtype=np.float32).reshape(-1)
        if int(source_rate) == int(target_rate):
            return pcm
        duration = pcm.size / float(source_rate)
        target_size = max(1, int(round(duration * target_rate)))
        source_positions = np.linspace(0.0, duration, pcm.size, endpoint=False)
        target_positions = np.linspace(0.0, duration, target_size, endpoint=False)
        return np.interp(target_positions, source_positions, pcm).astype(np.float32)

    @staticmethod
    def _normalize_for_inference(samples, target_rms=0.08, max_gain=30.0):
        """Raise quiet, non-silent audio to a stable level for YAMNet.

        A noise floor prevents silence and tiny ADC noise from being amplified.
        Peak limiting keeps the normalized waveform inside YAMNet's [-1, 1]
        input range.
        """
        pcm = np.asarray(samples, dtype=np.float32).reshape(-1)
        if pcm.size == 0:
            return pcm
        rms = float(np.sqrt(np.mean(np.square(pcm))))
        peak = float(np.max(np.abs(pcm)))
        if rms < 0.0008 or peak < 0.003:
            return pcm
        gain = min(float(max_gain), float(target_rms) / rms, 0.95 / peak)
        if gain <= 1.0:
            return pcm
        return (pcm * gain).astype(np.float32)


class AudioDetectionService:
    """Run fallback acoustic analysis and optional semantic classification."""

    def __init__(self, acoustic=None, semantic=None):
        self.acoustic = acoustic or AcousticAnomalyDetector()
        self.semantic = semantic or YamnetAudioClassifier()

    def analyze(self, samples, sample_rate: int) -> list[dict]:
        events = self.acoustic.analyze(samples, sample_rate)
        events.extend(self.semantic.analyze(samples, sample_rate))
        strongest = {}
        for event in events:
            label = event["label"]
            if label not in strongest or event["score"] > strongest[label]["score"]:
                strongest[label] = event
        return sorted(strongest.values(), key=lambda item: item["score"], reverse=True)

    def status(self):
        return {
            "lightweight": {"enabled": True, "loaded": True},
            "semantic": self.semantic.status(),
        }


class MultimodalFusionEngine:
    def __init__(self, window_seconds=5.0, trigger_threshold=0.65):
        self.window_seconds = float(window_seconds)
        self.trigger_threshold = float(trigger_threshold)
        self._audio = defaultdict(deque)
        self._emotion = defaultdict(deque)
        self._lock = threading.RLock()

    @staticmethod
    def _normal(value):
        return str(value or "").strip().lower().replace(" ", "_")

    def add_audio_event(self, camera_id, label, confidence, timestamp=None):
        event = (float(timestamp or time.time()), self._normal(label), self._confidence(confidence))
        with self._lock:
            self._audio[str(camera_id)].append(event)
            self._prune(str(camera_id), event[0])

    def add_emotion_event(self, camera_id, object_id, emotion, confidence, timestamp=None):
        event = (float(timestamp or time.time()), self._normal(emotion), self._confidence(confidence))
        key = (str(camera_id), str(object_id))
        with self._lock:
            self._emotion[key].append(event)
            self._prune(str(camera_id), event[0])

    def evaluate(self, camera_id, object_id=None, in_zone=False, timestamp=None):
        now = float(timestamp or time.time())
        camera_id = str(camera_id)
        key = (camera_id, str(object_id))
        with self._lock:
            self._prune(camera_id, now)
            audio_score, audio_label = self._max_risk(self._audio[camera_id], DISTRESS_AUDIO)
            immediate_audio_alarm = self._has_immediate_audio_alarm(self._audio[camera_id])
            emotion_score, emotion_label = self._max_risk(self._emotion[key], RISK_EMOTIONS)

        # A candidate from the lightweight detector is deliberately capped.
        if audio_label == "acoustic_distress_candidate":
            audio_score *= 0.65
        elif audio_label == "impact_candidate":
            audio_score *= 0.7

        zone_score = 1.0 if in_zone else 0.0
        score = 0.45 * audio_score + 0.25 * emotion_score + 0.30 * zone_score
        reasons = []
        if audio_score:
            reasons.append(f"audio:{audio_label}")
        if emotion_score:
            reasons.append(f"emotion:{emotion_label}")
        if in_zone:
            reasons.append("electronic_fence")

        # Cross-modal agreement is more reliable than any single weak cue.
        if audio_score >= 0.55 and emotion_score >= 0.55:
            score += 0.12
        if in_zone and emotion_score >= 0.65:
            score += 0.12
        if in_zone and audio_score >= 0.65:
            score += 0.12
        score = round(min(1.0, score), 4)
        strong_distress = audio_score >= 0.9
        triggered = score >= self.trigger_threshold or strong_distress or immediate_audio_alarm
        severity = "critical" if score >= 0.85 or strong_distress or immediate_audio_alarm else "high" if triggered else "medium"
        return FusionDecision(triggered, score, severity, tuple(reasons), round(audio_score, 4), round(emotion_score, 4), bool(in_zone))

    def snapshot(self, camera_id, object_id=None):
        decision = self.evaluate(camera_id, object_id, in_zone=False)
        return decision.to_dict()

    @staticmethod
    def _confidence(value):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("confidence must be finite")
        return max(0.0, min(1.0, value))

    @staticmethod
    def _max_risk(events, risk_map):
        best_score, best_label = 0.0, None
        for _, label, confidence in events:
            score = risk_map.get(label, 0.0) * confidence
            if label in ("acoustic_distress_candidate", "impact_candidate"):
                score = confidence
            if score > best_score:
                best_score, best_label = score, label
        return best_score, best_label

    @staticmethod
    def _has_immediate_audio_alarm(events):
        return any(
            confidence >= IMMEDIATE_AUDIO_ALARM_THRESHOLDS.get(label, float("inf"))
            for _, label, confidence in events
        )

    def _prune(self, camera_id, now):
        cutoff = now - self.window_seconds
        audio = self._audio[camera_id]
        while audio and audio[0][0] < cutoff:
            audio.popleft()
        for key in [key for key in self._emotion if key[0] == camera_id]:
            events = self._emotion[key]
            while events and events[0][0] < cutoff:
                events.popleft()
            if not events:
                self._emotion.pop(key, None)


fusion_engine = MultimodalFusionEngine()
acoustic_detector = AcousticAnomalyDetector()
semantic_detector = YamnetAudioClassifier()
audio_detection_service = AudioDetectionService(acoustic_detector, semantic_detector)
