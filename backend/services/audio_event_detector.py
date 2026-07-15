import csv
import json
import logging
import os
import queue
import shutil
import tarfile
import tempfile
import threading
import time
from collections import deque
from datetime import datetime
from math import gcd
from pathlib import Path

import numpy as np


logger = logging.getLogger(__name__)

DISPLAY_NAMES = {
    "explosion": "爆炸声",
    "glass_break": "玻璃破碎声",
}

CATEGORY_KEYWORDS = {
    "explosion": (
        "glass",
        "shatter",
        "breaking",
        "smash, crash",
        "crack",
        "chink, clink",
    ),
    "glass_break": (
        "explosion",
        "boom",
        "fireworks",
        "firecracker",
        "burst, pop",
        "eruption",
        "gunshot, gunfire",
        "machine gun",
        "fusillade",
        "artillery fire",
        "cap gun",
    ),
}


def merge_yamnet_class(class_name):
    normalized = str(class_name or "").strip().casefold()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if normalized in keywords:
            return category
    return None


class AcousticAnomalyDetector:
    """Report high-energy candidates without assigning semantic alarm labels."""

    def analyze(self, samples, sample_rate):
        pcm = np.asarray(samples, dtype=np.float32).reshape(-1)
        if sample_rate < 8000 or pcm.size < sample_rate // 4:
            return []

        peak = float(np.max(np.abs(pcm)))
        rms = float(np.sqrt(np.mean(np.square(pcm))))
        signs = np.signbit(pcm)
        zero_crossing_rate = float(np.mean(signs[1:] != signs[:-1]))
        crest = peak / max(rms, 1e-6)
        candidates = []

        distress_score = min(1.0, max(0.0, (rms - 0.08) * 4.5 + (zero_crossing_rate - 0.08) * 2.0))
        if peak > 0.35 and distress_score >= 0.35:
            candidates.append({"label": "acoustic_distress_candidate", "score": round(distress_score, 4)})

        impact_score = min(1.0, max(0.0, (crest - 4.0) / 8.0 + (peak - 0.6)))
        if peak > 0.65 and impact_score >= 0.35:
            candidates.append({"label": "impact_candidate", "score": round(impact_score, 4)})
        return candidates


class DetectionGate:
    def __init__(self, thresholds, confirmation_count=2, cooldown_seconds=3.0):
        self.thresholds = dict(thresholds)
        self.confirmation_count = max(1, int(confirmation_count))
        self.cooldown_seconds = max(0.0, float(cooldown_seconds))
        self._counts = {category: 0 for category in self.thresholds}
        self._last_triggered = {}

    def evaluate(self, category, confidence, now=None):
        now = time.monotonic() if now is None else float(now)
        if category not in self.thresholds:
            self._reset_counts()
            return False

        for other_category in self._counts:
            if other_category != category:
                self._counts[other_category] = 0

        if float(confidence) < float(self.thresholds[category]):
            self._counts[category] = 0
            return False

        self._counts[category] += 1
        if self._counts[category] < self.confirmation_count:
            return False

        self._counts[category] = 0
        last_triggered = self._last_triggered.get(category)
        if last_triggered is not None and now - last_triggered < self.cooldown_seconds:
            return False

        self._last_triggered[category] = now
        return True

    def _reset_counts(self):
        for category in self._counts:
            self._counts[category] = 0

    def reset_confirmation(self):
        self._reset_counts()


class AudioEventDetector:
    def __init__(self, app, config_path=None):
        self.app = app
        self.config_path = Path(config_path or Path(app.root_path) / "config" / "audio_detection.json")
        self.config = self._load_config()
        self.sample_rate = int(self.config.get("sample_rate", 16000))
        self.input_sample_rate = self.sample_rate
        self.selected_device = None
        self.window_samples = int(self.sample_rate * float(self.config.get("window_seconds", 0.96)))
        self.hop_samples = int(self.sample_rate * float(self.config.get("hop_seconds", 0.48)))
        self.gate = DetectionGate(
            self.config.get("thresholds", {}),
            self.config.get("confirmation_count", 2),
            self.config.get("cooldown_seconds", 3.0),
        )
        self.acoustic_detector = AcousticAnomalyDetector()
        self.model = None
        self.class_names = None
        self._stream = None
        self._worker = None
        self._running = False
        self._audio_queue = queue.Queue(maxsize=20)
        self._waveform = deque(maxlen=self.window_samples)
        self._lock = threading.RLock()
        self._last_result = None
        self._last_triggered_result = None
        self._last_triggered_monotonic = None
        self.display_hold_seconds = max(0.0, float(self.config.get("display_hold_seconds", 5.0)))
        self._dropped_chunks = 0
        self._coalesced_chunks = 0
        self._last_inference_ms = None
        self._last_error = None
        self._alert_logger = self._build_alert_logger()

    def _load_config(self):
        try:
            with self.config_path.open("r", encoding="utf-8") as config_file:
                return json.load(config_file)
        except FileNotFoundError as exc:
            raise RuntimeError(f"声音检测配置文件不存在：{self.config_path}") from exc
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"声音检测配置文件无法读取：{exc}") from exc

    def _build_alert_logger(self):
        log_path = Path(self.config.get("log_file", "logs/audio_alerts.log"))
        if not log_path.is_absolute():
            log_path = Path(self.app.root_path) / log_path
        log_path.parent.mkdir(parents=True, exist_ok=True)
        alert_logger = logging.getLogger(f"audio_alerts.{id(self.app)}")
        alert_logger.setLevel(logging.INFO)
        alert_logger.propagate = False
        if not alert_logger.handlers:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
            alert_logger.addHandler(handler)
        return alert_logger

    def _load_model(self):
        if self.model is not None:
            return
        cache_dir = Path(self.config.get("model_cache_dir", "core_cv/weights/tfhub"))
        if not cache_dir.is_absolute():
            cache_dir = Path(self.app.root_path) / cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("TFHUB_CACHE_DIR", str(cache_dir))
        try:
            import tensorflow_hub as hub
        except (ImportError, ModuleNotFoundError) as exc:
            raise RuntimeError(
                "YAMNet 依赖不可用，请执行 pip install -r backend/requirements-audio.txt。"
                f"原始错误：{exc}"
            ) from exc

        model_url = self.config.get("model_url", "https://tfhub.dev/google/yamnet/1")
        local_model_dir = Path(self.config.get("local_model_dir", "core_cv/weights/yamnet"))
        if not local_model_dir.is_absolute():
            local_model_dir = Path(self.app.root_path) / local_model_dir
        logger.info("Loading YAMNet model from %s", model_url)
        if (local_model_dir / "saved_model.pb").is_file():
            self.model = hub.load(str(local_model_dir))
        else:
            try:
                self.model = hub.load(model_url)
            except Exception as hub_error:
                logger.warning("TensorFlow Hub direct load failed: %s", hub_error)
                self._download_yamnet(model_url, local_model_dir)
                self.model = hub.load(str(local_model_dir))

        class_map_path = self.model.class_map_path().numpy()
        if isinstance(class_map_path, bytes):
            class_map_path = class_map_path.decode("utf-8")
        with open(class_map_path, newline="", encoding="utf-8") as class_map_file:
            self.class_names = [row["display_name"] for row in csv.DictReader(class_map_file)]
        logger.info("YAMNet loaded with %s classes", len(self.class_names))

    def _download_yamnet(self, model_url, destination):
        import requests

        if destination.exists() and not (destination / "saved_model.pb").is_file():
            raise RuntimeError(f"YAMNet 本地目录不完整，请检查后重试：{destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        download_url = f"{model_url}?tf-hub-format=compressed"
        try:
            with tempfile.TemporaryDirectory(dir=destination.parent) as temporary_dir:
                temporary_path = Path(temporary_dir)
                archive_path = temporary_path / "yamnet.tar.gz"
                logger.info("Downloading YAMNet archive from %s", download_url)
                with requests.get(download_url, stream=True, timeout=(15, 120)) as response:
                    response.raise_for_status()
                    with archive_path.open("wb") as archive_file:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                archive_file.write(chunk)

                extracted_path = temporary_path / "extracted"
                extracted_path.mkdir()
                with tarfile.open(archive_path, "r:gz") as archive:
                    archive.extractall(extracted_path, filter="data")
                saved_models = list(extracted_path.rglob("saved_model.pb"))
                if len(saved_models) != 1:
                    raise RuntimeError("YAMNet 压缩包中未找到唯一的 saved_model.pb")
                shutil.move(str(saved_models[0].parent), str(destination))
                logger.info("YAMNet downloaded to %s", destination)
        except Exception as exc:
            raise RuntimeError(
                "YAMNet 模型下载失败，请检查网络后重试。"
                f"目标目录：{destination}。原始错误：{exc}"
            ) from exc

    def list_devices(self):
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "未安装麦克风采集依赖 sounddevice，请安装 backend/requirements-audio.txt"
            ) from exc
        devices = []
        for index, device in enumerate(sd.query_devices()):
            if int(device.get("max_input_channels", 0)) > 0:
                devices.append({
                    "id": index,
                    "name": device.get("name", f"Input {index}"),
                    "channels": int(device.get("max_input_channels", 0)),
                    "default_sample_rate": float(device.get("default_samplerate", 0)),
                })
        return devices

    def start(self, device=None):
        with self._lock:
            if self._running:
                return self.status()
            self._last_error = None

        self._load_model()
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError(
                "未安装麦克风采集依赖 sounddevice，请安装 backend/requirements-audio.txt"
            ) from exc

        selected_device = self.config.get("input_device") if device is None else device
        self.gate.reset_confirmation()
        try:
            device_info = sd.query_devices(selected_device, "input")
            input_sample_rate = int(round(float(device_info["default_samplerate"])))
            input_blocksize = int(input_sample_rate * float(self.config.get("hop_seconds", 0.48)))
            with self._lock:
                self.input_sample_rate = input_sample_rate
                self.selected_device = selected_device
            stream = sd.InputStream(
                device=selected_device,
                samplerate=input_sample_rate,
                channels=1,
                dtype="float32",
                blocksize=input_blocksize,
                callback=self._audio_callback,
            )
            stream.start()
        except Exception as exc:
            raise RuntimeError(f"无法打开麦克风，请检查设备连接和系统权限：{exc}") from exc

        with self._lock:
            self._stream = stream
            self._waveform.clear()
            self._running = True
            self._worker = threading.Thread(
                target=self._run_loop,
                name="YAMNetAudioDetector",
                daemon=True,
            )
            self._worker.start()
        logger.info("Audio detection started with device=%s", selected_device)
        return self.status()

    def stop(self):
        with self._lock:
            self._running = False
            stream = self._stream
            worker = self._worker
            self._stream = None
            self._worker = None
            self.gate.reset_confirmation()
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception as exc:
                logger.warning("Failed to close microphone cleanly: %s", exc)
        if worker is not None and worker is not threading.current_thread():
            worker.join(timeout=3.0)
        while True:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.task_done()
            except queue.Empty:
                break
        logger.info("Audio detection stopped")
        return self.status()

    def status(self):
        with self._lock:
            display_result = self._last_result
            if (
                self._last_triggered_result is not None
                and self._last_triggered_monotonic is not None
                and time.monotonic() - self._last_triggered_monotonic < self.display_hold_seconds
            ):
                display_result = self._last_triggered_result
            return {
                "running": self._running,
                "sample_rate": self.sample_rate,
                "input_sample_rate": self.input_sample_rate,
                "selected_device": self.selected_device,
                "window_seconds": self.window_samples / self.sample_rate,
                "hop_seconds": self.hop_samples / self.sample_rate,
                "thresholds": dict(self.gate.thresholds),
                "confirmation_count": self.gate.confirmation_count,
                "cooldown_seconds": self.gate.cooldown_seconds,
                "display_hold_seconds": self.display_hold_seconds,
                "audio_queue_size": self._audio_queue.qsize(),
                "dropped_chunks": self._dropped_chunks,
                "coalesced_chunks": self._coalesced_chunks,
                "last_inference_ms": self._last_inference_ms,
                "last_result": display_result,
                "last_triggered_result": self._last_triggered_result,
                "last_error": self._last_error,
            }

    def _audio_callback(self, indata, frames, time_info, status):
        if status:
            logger.warning("Microphone status: %s", status)
        chunk = np.asarray(indata[:, 0], dtype=np.float32).copy()
        try:
            self._audio_queue.put_nowait(chunk)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
                self._audio_queue.task_done()
                with self._lock:
                    self._dropped_chunks += 1
            except queue.Empty:
                pass
            try:
                self._audio_queue.put_nowait(chunk)
            except queue.Full:
                logger.warning("Audio queue is full; dropping microphone chunk")

    def _run_loop(self):
        while True:
            with self._lock:
                if not self._running:
                    return
            try:
                chunk = self._audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                chunk = self._coalesce_pending_chunks(chunk)
                chunk = self._resample_for_model(chunk)
                self._waveform.extend(chunk.tolist())
                if len(self._waveform) >= self.window_samples:
                    waveform = np.asarray(self._waveform, dtype=np.float32)
                    inference_started_at = time.monotonic()
                    result = self.analyze_waveform(waveform)
                    self._handle_result(result)
                    with self._lock:
                        self._last_inference_ms = round(
                            (time.monotonic() - inference_started_at) * 1000.0,
                            1,
                        )
            except Exception as exc:
                with self._lock:
                    self._last_error = str(exc)
                logger.exception("YAMNet microphone inference failed")
            finally:
                self._audio_queue.task_done()

    def _coalesce_pending_chunks(self, first_chunk):
        chunks = [np.asarray(first_chunk, dtype=np.float32)]
        while True:
            try:
                chunks.append(np.asarray(self._audio_queue.get_nowait(), dtype=np.float32))
                self._audio_queue.task_done()
            except queue.Empty:
                break

        if len(chunks) > 1:
            with self._lock:
                self._coalesced_chunks += len(chunks) - 1
            return np.concatenate(chunks)
        return chunks[0]

    def _resample_for_model(self, chunk):
        chunk = np.asarray(chunk, dtype=np.float32)
        if self.input_sample_rate == self.sample_rate:
            return chunk

        from scipy.signal import resample_poly

        divisor = gcd(self.input_sample_rate, self.sample_rate)
        resampled = resample_poly(
            chunk,
            self.sample_rate // divisor,
            self.input_sample_rate // divisor,
        )
        return np.asarray(resampled, dtype=np.float32)

    def analyze_waveform(self, waveform):
        self._load_model()
        waveform = np.asarray(waveform, dtype=np.float32).reshape(-1)
        acoustic_candidates = self.acoustic_detector.analyze(waveform, self.sample_rate)
        inference_waveform = self._normalize_for_inference(waveform)
        scores, embeddings, spectrogram = self.model(inference_waveform)
        score_values = np.asarray(scores.numpy(), dtype=np.float32)
        mean_scores = score_values.mean(axis=0)
        top_index = int(np.argmax(mean_scores))
        raw_class = self.class_names[top_index]
        raw_confidence = float(mean_scores[top_index])
        top_indices = np.argsort(mean_scores)[-5:][::-1]
        top_predictions = [
            {
                "class_name": self.class_names[int(index)],
                "confidence": float(mean_scores[index]),
            }
            for index in top_indices
        ]

        grouped = {category: {"confidence": 0.0, "raw_class": None} for category in CATEGORY_KEYWORDS}
        for index, class_name in enumerate(self.class_names):
            category = merge_yamnet_class(class_name)
            if category is None:
                continue
            confidence = float(np.max(score_values[:, index]))
            if confidence > grouped[category]["confidence"]:
                grouped[category] = {"confidence": confidence, "raw_class": class_name}

        candidate_category = max(grouped, key=lambda key: grouped[key]["confidence"])
        candidate = grouped[candidate_category]
        threshold = float(self.gate.thresholds.get(candidate_category, 1.0))
        category = candidate_category if candidate["confidence"] >= threshold else None

        return {
            "category": category,
            "display_name": DISPLAY_NAMES.get(category, "其他声音"),
            "confidence": candidate["confidence"],
            "matched_raw_class": candidate["raw_class"],
            "raw_class": raw_class,
            "raw_confidence": raw_confidence,
            "top_predictions": top_predictions,
            "acoustic_candidates": acoustic_candidates,
            "explosion_score": grouped["explosion"]["confidence"],
            "glass_break_score": grouped["glass_break"]["confidence"],
            "detected_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "embedding": np.asarray(embeddings.numpy(), dtype=np.float32),
        }

    def extract_embeddings(self, waveform):
        embeddings = self.analyze_waveform(waveform)["embedding"]
        return np.asarray(embeddings, dtype=np.float32).mean(axis=0)

    def _handle_result(self, result):
        public_result = {key: value for key, value in result.items() if key != "embedding"}
        triggered = self.gate.evaluate(result["category"], result["confidence"])
        public_result["triggered"] = triggered
        with self._lock:
            self._last_result = public_result
            if triggered:
                self._last_triggered_result = dict(public_result)
                self._last_triggered_monotonic = time.monotonic()

        logger.info(
            "声音识别 result=%s confidence=%.3f raw=%s raw_confidence=%.3f "
            "explosion_score=%.3f glass_break_score=%.3f triggered=%s time=%s",
            public_result["display_name"],
            public_result["confidence"],
            public_result["raw_class"],
            public_result["raw_confidence"],
            public_result["explosion_score"],
            public_result["glass_break_score"],
            triggered,
            public_result["detected_at"],
        )
        logger.info(
            "Top 5 YAMNet predictions: %s",
            ", ".join(
                f"{prediction['class_name']}={prediction['confidence']:.3f}"
                for prediction in public_result["top_predictions"]
            ),
        )
        if public_result["acoustic_candidates"]:
            logger.info("Acoustic candidates: %s", public_result["acoustic_candidates"])
        if triggered:
            logger.warning(
                "========== 检测到%s confidence=%.3f YAMNet=%s ==========" ,
                public_result["display_name"],
                public_result["confidence"],
                public_result["matched_raw_class"],
            )
            self._alert_logger.info(
                "检测到%s confidence=%.3f yamnet_class=%s",
                public_result["display_name"],
                public_result["confidence"],
                public_result["matched_raw_class"],
            )
            self._enqueue_alarm(public_result)

    @staticmethod
    def _normalize_for_inference(samples, target_rms=0.08, max_gain=30.0):
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
        return np.asarray(pcm * gain, dtype=np.float32)

    def _enqueue_alarm(self, result):
        import cv2
        from core_cv.pipeline import alarm_queue

        camera_id = str(self.config.get("camera_id", "cam-1"))
        snapshot_frame = None
        manager = self.app.config.get("pipeline_manager")
        if manager is not None:
            pipeline = manager.pipelines.get(camera_id)
            if pipeline is not None:
                with pipeline.frame_lock:
                    if pipeline.latest_processed_frame is not None:
                        snapshot_frame = pipeline.latest_processed_frame.copy()
        if snapshot_frame is None:
            snapshot_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            cv2.putText(
                snapshot_frame,
                "Audio event detected",
                (60, 100),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 0, 255),
                2,
            )

        alarm_data = {
            "alarm_type": "异常声音告警",
            "level": "critical" if result["category"] == "explosion" else "high",
            "camera_id": camera_id,
            "coordinate": None,
            "snapshot_frame": snapshot_frame,
            "name": result["display_name"],
            "object_id": None,
            "description": f"检测到{result['display_name']}",
            "triggered_at": datetime.utcnow(),
            "triggered_monotonic": time.monotonic(),
            "detection_data": {
                "type": "audio_event",
                "category": result["category"],
                "confidence": result["confidence"],
                "yamnet_class": result["matched_raw_class"],
                "detected_at": result["detected_at"],
            },
        }
        try:
            alarm_queue.put_nowait(alarm_data)
            logger.info("Audio alarm pushed to alarm_queue: %s", result["display_name"])
        except queue.Full:
            logger.error("alarm_queue is full; audio alarm was dropped")


_detectors = {}
_detectors_lock = threading.Lock()


def get_audio_event_detector(app):
    app_object = app._get_current_object() if hasattr(app, "_get_current_object") else app
    key = id(app_object)
    with _detectors_lock:
        detector = _detectors.get(key)
        if detector is None:
            detector = AudioEventDetector(app_object)
            _detectors[key] = detector
        return detector
