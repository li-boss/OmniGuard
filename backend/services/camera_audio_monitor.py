"""Background audio-track monitor for RTSP/RTMP camera sources."""

from __future__ import annotations

import logging
import subprocess
import threading
import time

import numpy as np

from models import AlarmEvent, db
from services.multimodal_fusion import audio_detection_service, fusion_engine
from services.ws_handler import push_alarm


logger = logging.getLogger(__name__)


class CameraAudioMonitor:
    def __init__(self, app):
        self.app = app
        self.enabled = bool(app.config.get("CAMERA_AUDIO_MONITOR_ENABLED", False))
        self.ffmpeg = app.config.get("FFMPEG_PATH", "ffmpeg")
        self.chunk_seconds = float(app.config.get("AUDIO_CHUNK_SECONDS", 0.5))
        self.cooldown_seconds = float(app.config.get("AUDIO_ALARM_COOLDOWN_SECONDS", 30))
        self.running = False
        self._manager_thread = None
        self._workers = {}
        self._processes = {}
        self._statuses = {}
        self._last_alarm_at = {}
        self._lock = threading.RLock()

    def start(self):
        if not self.enabled or self.running:
            return
        self.running = True
        self._manager_thread = threading.Thread(
            target=self._manager_loop,
            name="CameraAudioMonitor-Manager",
            daemon=True,
        )
        self._manager_thread.start()
        logger.info("Camera audio-track monitoring enabled")

    def stop(self):
        self.running = False
        with self._lock:
            processes = list(self._processes.values())
        for process in processes:
            self._terminate(process)
        if self._manager_thread:
            self._manager_thread.join(timeout=3)
            self._manager_thread = None

    def status(self):
        with self._lock:
            cameras = {camera_id: dict(value) for camera_id, value in self._statuses.items()}
        return {"enabled": self.enabled, "running": self.running, "cameras": cameras}

    def _manager_loop(self):
        while self.running:
            try:
                from core_cv.pipeline import load_camera_streams

                sources = load_camera_streams()
                for camera_id, source in sources.items():
                    source = str(source)
                    if not source.lower().startswith(("rtsp://", "rtmp://", "http://", "https://")):
                        continue
                    with self._lock:
                        worker = self._workers.get(camera_id)
                    if worker is None or not worker.is_alive():
                        worker = threading.Thread(
                            target=self._worker_loop,
                            args=(str(camera_id), source),
                            name=f"CameraAudioMonitor-{camera_id}",
                            daemon=True,
                        )
                        with self._lock:
                            self._workers[camera_id] = worker
                        worker.start()
            except Exception as exc:
                logger.warning("Unable to synchronize camera audio sources: %s", exc)
            self._wait(5.0)

    def _worker_loop(self, camera_id, source):
        sample_rate = 16000
        chunk_bytes = max(2, int(sample_rate * self.chunk_seconds) * 2)
        while self.running:
            command = [
                self.ffmpeg,
                "-nostdin",
                "-loglevel", "error",
                "-i", source,
                "-vn",
                "-ac", "1",
                "-ar", str(sample_rate),
                "-f", "s16le",
                "pipe:1",
            ]
            process = None
            try:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    bufsize=chunk_bytes * 2,
                )
                with self._lock:
                    self._processes[camera_id] = process
                    self._statuses[camera_id] = {
                        "connected": False,
                        "state": "connecting",
                        "source": source,
                        "error": None,
                    }
                while self.running and process.poll() is None:
                    raw = self._read_chunk(process.stdout, chunk_bytes)
                    if len(raw) < chunk_bytes:
                        break
                    with self._lock:
                        self._statuses[camera_id].update({"connected": True, "state": "streaming"})
                    samples = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
                    events = audio_detection_service.analyze(samples, sample_rate)
                    self._handle_events(camera_id, events)
            except FileNotFoundError:
                self._set_error(camera_id, f"FFmpeg executable not found: {self.ffmpeg}")
                logger.error("FFmpeg is required for camera audio-track monitoring")
                return
            except Exception as exc:
                self._set_error(camera_id, str(exc))
                logger.warning("Camera %s audio monitor failed: %s", camera_id, exc)
            finally:
                if process is not None:
                    self._terminate(process)
                with self._lock:
                    self._processes.pop(camera_id, None)
                    status = self._statuses.setdefault(camera_id, {"source": source})
                    status["connected"] = False
                    status["state"] = "reconnecting" if self.running else "stopped"
            self._wait(3.0)

    def _handle_events(self, camera_id, events):
        if not events:
            return
        for event in events:
            fusion_engine.add_audio_event(camera_id, event["label"], event["score"])
        decision = fusion_engine.evaluate(camera_id)
        if not decision.triggered:
            return
        now = time.time()
        with self._lock:
            if now - self._last_alarm_at.get(camera_id, 0.0) < self.cooldown_seconds:
                return
            self._last_alarm_at[camera_id] = now
        with self.app.app_context():
            alarm = AlarmEvent(
                alarm_type="multimodal_anomaly",
                severity=decision.severity,
                camera_id=camera_id,
                description="摄像头音轨检测到异常声音",
                detection_data={**decision.to_dict(), "audio_events": events, "source": "camera_audio_track"},
                status="pending",
            )
            db.session.add(alarm)
            db.session.commit()
            push_alarm(alarm.to_dict())

    def _set_error(self, camera_id, message):
        with self._lock:
            status = self._statuses.setdefault(camera_id, {})
            status.update({"connected": False, "state": "error", "error": message})

    def _wait(self, seconds):
        deadline = time.time() + seconds
        while self.running and time.time() < deadline:
            time.sleep(min(0.2, deadline - time.time()))

    @staticmethod
    def _read_chunk(stream, expected):
        data = bytearray()
        while len(data) < expected:
            part = stream.read(expected - len(data))
            if not part:
                break
            data.extend(part)
        return bytes(data)

    @staticmethod
    def _terminate(process):
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
