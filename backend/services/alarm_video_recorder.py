import logging
import os
import queue
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2


logger = logging.getLogger(__name__)
_video_writer_init_lock = threading.Lock()


@dataclass
class _Recording:
    alarm_id: int
    camera_id: str
    earliest_frame_time: float
    deadline: float
    abs_path: Path
    public_path: str
    writer: object = None
    frames_received: int = 0
    frames_written: int = 0
    frames_dropped: int = 0
    writer_init_attempts: int = 0
    writer_init_failed: bool = False
    writer_initializing: bool = False
    writer_init_thread: object = None
    finish_requested: bool = False
    finish_attach_to_alarm: bool = True
    pending_frames: object = field(default_factory=deque, repr=False)
    stopped: bool = False
    io_lock: object = field(default_factory=threading.RLock, repr=False)


class AlarmVideoRecorder:
    """Asynchronously records alarm evidence from frames already read by a pipeline."""

    def __init__(self, app):
        self.app = app
        self.duration_seconds = float(app.config.get("ALARM_VIDEO_POST_SECONDS", 10))
        self.pre_buffer_seconds = float(app.config.get("ALARM_VIDEO_PRE_SECONDS", 5))
        self.fps = float(app.config.get("ALARM_VIDEO_FPS", 10))
        self.video_dir = Path(app.root_path) / "static" / "videos"
        self.video_dir.mkdir(parents=True, exist_ok=True)

        self._recordings = {}
        self._lock = threading.RLock()
        self._frames = queue.Queue(maxsize=int(app.config.get("ALARM_VIDEO_QUEUE_SIZE", 300)))
        self._sample_interval = 1.0 / max(self.fps, 0.1)
        self._pre_buffer_frames = max(1, int(self.pre_buffer_seconds * self.fps) + 2)
        self._pre_buffers = defaultdict(lambda: deque(maxlen=self._pre_buffer_frames))
        self._last_sample_at = {}
        self._accepting_frames = True
        self._running = True
        self._thread = threading.Thread(
            target=self._run,
            name="AlarmVideoRecorderThread",
            daemon=True,
        )
        self._thread.start()
        self._compat_thread = None

    def start_recording(
        self,
        alarm_id,
        camera_id,
        triggered_monotonic=None,
        trigger_frame=None,
    ):
        triggered_monotonic = triggered_monotonic or time.monotonic()
        filename = f"alarm_{alarm_id}.mp4"
        recording = _Recording(
            alarm_id=alarm_id,
            camera_id=str(camera_id),
            earliest_frame_time=triggered_monotonic - self.pre_buffer_seconds,
            deadline=triggered_monotonic + self.duration_seconds,
            abs_path=self.video_dir / filename,
            public_path=f"/static/videos/{filename}",
            pending_frames=deque(
                maxlen=max(
                    1,
                    int((self.pre_buffer_seconds + self.duration_seconds) * self.fps) + 2,
                )
            ),
        )
        with self._lock:
            if not self._accepting_frames:
                return
            previous = self._recordings.pop(alarm_id, None)
            if previous:
                self._finish(previous)
            self._recordings[alarm_id] = recording
            pre_buffer_start = triggered_monotonic - self.pre_buffer_seconds
            trigger_cutoff = triggered_monotonic - (self._sample_interval / 2.0)
            for captured_at, buffered_frame in self._pre_buffers[str(camera_id)]:
                if pre_buffer_start <= captured_at <= trigger_cutoff:
                    self._enqueue_frame(
                        str(camera_id),
                        captured_at,
                        buffered_frame.copy(),
                        target_alarm_ids={alarm_id},
                    )
            if trigger_frame is not None:
                self._enqueue_frame(
                    str(camera_id),
                    triggered_monotonic,
                    trigger_frame.copy(),
                    target_alarm_ids={alarm_id},
                )
        logger.info("Started alarm video recording for alarm %s", alarm_id)

    def submit_frame(self, camera_id, frame):
        if frame is None:
            return
        camera_id = str(camera_id)
        captured_at = time.monotonic()
        with self._lock:
            if not self._accepting_frames:
                return
            last_sample_at = self._last_sample_at.get(camera_id)
            if last_sample_at is not None and captured_at - last_sample_at < self._sample_interval:
                return
            self._last_sample_at[camera_id] = captured_at
            sampled_frame = frame.copy()
            self._pre_buffers[camera_id].append((captured_at, sampled_frame))
            interested = any(r.camera_id == camera_id for r in self._recordings.values())
            if interested:
                self._enqueue_frame(camera_id, captured_at, sampled_frame.copy())

    def _enqueue_frame(self, camera_id, captured_at, frame, target_alarm_ids=None):
        try:
            self._frames.put_nowait((camera_id, captured_at, frame, target_alarm_ids))
        except queue.Full:
            try:
                self._frames.get_nowait()
            except queue.Empty:
                pass
            else:
                self._frames.task_done()

            try:
                self._frames.put_nowait((camera_id, captured_at, frame, target_alarm_ids))
                logger.warning(
                    "Alarm video frame queue is full; dropped the oldest frame for %s",
                    camera_id,
                )
            except queue.Full:
                logger.warning(
                    "Alarm video frame queue remained full; dropping the latest frame for %s",
                    camera_id,
                )

    def stop(self):
        with self._lock:
            self._accepting_frames = False
        self._frames.join()
        self._running = False
        self._thread.join(timeout=3.0)
        if self._compat_thread is not None:
            self._compat_thread.join(timeout=3.0)
        with self._lock:
            recordings = list(self._recordings.values())
            self._recordings.clear()
        for recording in recordings:
            self._finish(recording)
        for recording in recordings:
            self._wait_for_writer_initialization(recording)
            self._finish(recording)

    def stop_recording(self, alarm_id):
        with self._lock:
            recording = self._recordings.pop(alarm_id, None)
        if recording is None:
            return False
        self._finish(recording, attach_to_alarm=False)
        self._wait_for_writer_initialization(recording)
        self._finish(recording, attach_to_alarm=False)
        return True

    @staticmethod
    def _codec_name(capture):
        value = int(capture.get(cv2.CAP_PROP_FOURCC))
        return "".join(chr((value >> (8 * index)) & 0xFF) for index in range(4)).lower()

    def _transcode_existing_videos(self):
        """Safely migrate legacy mp4v/FMP4 clips to browser-compatible H.264."""
        for video_path in sorted(self.video_dir.glob("*.mp4")):
            if video_path.stem.endswith("_browser"):
                continue
            browser_path = video_path.with_name(f"{video_path.stem}_browser.mp4")
            temp_path = video_path.with_name(f".{video_path.stem}.h264.tmp.mp4")
            capture = cv2.VideoCapture(os.fspath(video_path))
            writer = None
            try:
                if not capture.isOpened():
                    logger.warning("Unable to inspect legacy alarm video: %s", video_path)
                    continue
                if self._codec_name(capture) in {"h264", "avc1"}:
                    continue
                if self._is_valid_h264_video(browser_path):
                    self._attach_compatible_path(video_path, browser_path)
                    continue

                width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = capture.get(cv2.CAP_PROP_FPS) or self.fps
                if width <= 0 or height <= 0:
                    logger.warning("Invalid legacy alarm video dimensions: %s", video_path)
                    continue

                with _video_writer_init_lock:
                    writer = cv2.VideoWriter(
                        os.fspath(temp_path),
                        cv2.VideoWriter_fourcc(*"avc1"),
                        fps,
                        (width, height),
                    )
                    writer_opened = writer.isOpened()
                if not writer_opened:
                    logger.warning("H.264 encoder unavailable; keeping legacy video: %s", video_path)
                    continue

                frames_written = 0
                while self._running:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    writer.write(frame)
                    frames_written += 1

                writer.release()
                writer = None
                capture.release()

                if frames_written == 0 or not self._is_valid_h264_video(temp_path):
                    logger.warning("Converted video failed validation; keeping original: %s", video_path)
                    continue

                os.replace(temp_path, browser_path)
                self._attach_compatible_path(video_path, browser_path)
                logger.info(
                    "Created browser-compatible H.264 copy %s; preserved legacy file %s",
                    browser_path,
                    video_path,
                )
            except Exception:
                logger.exception("Failed to convert legacy alarm video: %s", video_path)
            finally:
                capture.release()
                if writer is not None:
                    writer.release()
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        logger.warning("Unable to remove temporary video: %s", temp_path)

    def _is_valid_h264_video(self, video_path):
        if not video_path.is_file():
            return False
        capture = cv2.VideoCapture(os.fspath(video_path))
        try:
            if not capture.isOpened() or self._codec_name(capture) not in {"h264", "avc1"}:
                return False
            ok, frame = capture.read()
            return ok and frame is not None and frame.size > 0
        finally:
            capture.release()

    def _attach_compatible_path(self, legacy_path, browser_path):
        from models import AlarmEvent, db

        legacy_public_path = f"/static/videos/{legacy_path.name}"
        browser_public_path = f"/static/videos/{browser_path.name}"
        with self.app.app_context():
            alarms = AlarmEvent.query.filter(
                (AlarmEvent.video_path == legacy_public_path)
                | (AlarmEvent.clip_url == legacy_public_path)
            ).all()
            for alarm in alarms:
                alarm.video_path = browser_public_path
                alarm.clip_url = browser_public_path
            if alarms:
                db.session.commit()

    def _run(self):
        while self._running:
            try:
                camera_id, captured_at, frame, target_alarm_ids = self._frames.get(timeout=0.25)
            except queue.Empty:
                self._finish_expired(time.monotonic())
                continue

            try:
                with self._lock:
                    recordings = [
                        r for r in self._recordings.values()
                        if r.camera_id == camera_id
                        and r.earliest_frame_time <= captured_at
                        and captured_at <= r.deadline
                        and (target_alarm_ids is None or r.alarm_id in target_alarm_ids)
                    ]
                for recording in recordings:
                    self._write_frame(recording, frame)
                self._finish_expired(captured_at)
            except Exception:
                logger.exception("Failed to process an alarm video frame")
            finally:
                self._frames.task_done()

    def _write_frame(self, recording, frame):
        with recording.io_lock:
            if recording.stopped:
                return

            recording.frames_received += 1
            if recording.writer is not None:
                recording.writer.write(frame)
                recording.frames_written += 1
                return
            if recording.writer_init_failed:
                return

            if len(recording.pending_frames) == recording.pending_frames.maxlen:
                recording.frames_dropped += 1
            recording.pending_frames.append(frame)

            if not recording.writer_initializing:
                height, width = frame.shape[:2]
                recording.writer_initializing = True
                recording.writer_init_attempts += 1
                thread = threading.Thread(
                    target=self._create_writer,
                    args=(recording, width, height),
                    name=f"AlarmVideoWriterInit-{recording.alarm_id}",
                    daemon=True,
                )
                recording.writer_init_thread = thread
                thread.start()

    def _create_writer(self, recording, width, height):
        started_at = time.time()
        started_monotonic = time.monotonic()
        logger.info(
            "Alarm video writer initialization started: alarm_id=%s started_at=%.3f attempt=%s",
            recording.alarm_id,
            started_at,
            recording.writer_init_attempts,
        )

        writer = None
        writer_opened = False
        try:
            # H.264 in an MP4 container is supported by modern browsers. The
            # previous mp4v/FMP4 output contained valid frames but rendered as
            # a black video in Chromium-based browsers.
            fourcc = cv2.VideoWriter_fourcc(*"avc1")
            with _video_writer_init_lock:
                writer = cv2.VideoWriter(
                    os.fspath(recording.abs_path), fourcc, self.fps, (width, height)
                )
                writer_opened = writer.isOpened()
        except Exception:
            logger.exception(
                "Alarm video writer initialization failed: alarm_id=%s path=%s",
                recording.alarm_id,
                recording.abs_path,
            )

        elapsed = time.monotonic() - started_monotonic
        logger.info(
            "Alarm video writer initialization finished: alarm_id=%s finished_at=%.3f "
            "elapsed=%.3fs opened=%s",
            recording.alarm_id,
            time.time(),
            elapsed,
            writer_opened,
        )

        finish_requested = False
        finish_attach_to_alarm = True
        with recording.io_lock:
            recording.writer_initializing = False
            if recording.stopped:
                if writer is not None:
                    writer.release()
                return

            if writer_opened:
                recording.writer = writer
                while recording.pending_frames:
                    recording.writer.write(recording.pending_frames.popleft())
                    recording.frames_written += 1
            else:
                if writer is not None:
                    writer.release()
                if recording.writer_init_attempts >= 3:
                    recording.writer_init_failed = True
                    logger.error(
                        "Unable to open video writer after %s attempts; giving up for alarm %s: %s",
                        recording.writer_init_attempts,
                        recording.alarm_id,
                        recording.abs_path,
                    )
                else:
                    logger.warning(
                        "Unable to open video writer for alarm %s (attempt %s/3): %s",
                        recording.alarm_id,
                        recording.writer_init_attempts,
                        recording.abs_path,
                    )

            finish_requested = recording.finish_requested
            finish_attach_to_alarm = recording.finish_attach_to_alarm

        if finish_requested:
            self._finish(recording, attach_to_alarm=finish_attach_to_alarm)

    @staticmethod
    def _wait_for_writer_initialization(recording):
        while True:
            with recording.io_lock:
                thread = recording.writer_init_thread
                initializing = recording.writer_initializing
            if not initializing or thread is None or thread is threading.current_thread():
                return
            thread.join()

    def _finish_expired(self, now):
        with self._lock:
            recordings = [
                recording for recording in self._recordings.values()
                if now >= recording.deadline
            ]
        for recording in recordings:
            self._finish(recording)
            with self._lock:
                if (
                    recording.stopped
                    and self._recordings.get(recording.alarm_id) is recording
                ):
                    self._recordings.pop(recording.alarm_id, None)

    def _finish(self, recording, attach_to_alarm=True):
        with recording.io_lock:
            if recording.stopped:
                return
            if recording.writer_initializing:
                recording.finish_requested = True
                if not attach_to_alarm:
                    recording.finish_attach_to_alarm = False
                return
            recording.stopped = True
            if recording.writer is not None:
                recording.writer.release()
                recording.writer = None
            recording.pending_frames.clear()
        logger.info(
            "Finished alarm video recording: alarm_id=%s frames_received=%s "
            "frames_written=%s frames_dropped=%s",
            recording.alarm_id,
            recording.frames_received,
            recording.frames_written,
            recording.frames_dropped,
        )
        if recording.frames_written == 0 or not recording.abs_path.is_file():
            logger.warning("No video frames captured for alarm %s", recording.alarm_id)
            return
        if not attach_to_alarm:
            return

        try:
            from models import AlarmEvent, db

            with self.app.app_context():
                alarm = db.session.get(AlarmEvent, recording.alarm_id)
                if alarm:
                    alarm.video_path = recording.public_path
                    alarm.clip_url = recording.public_path
                    db.session.commit()
                    logger.info("Alarm video saved to %s", recording.abs_path)
        except Exception:
            with self.app.app_context():
                from models import db
                db.session.rollback()
            logger.exception("Failed to attach video to alarm %s", recording.alarm_id)


_recorders = {}
_recorders_lock = threading.Lock()


def get_alarm_video_recorder(app):
    key = id(app)
    with _recorders_lock:
        recorder = _recorders.get(key)
        if recorder is None:
            recorder = AlarmVideoRecorder(app)
            _recorders[key] = recorder
        return recorder


def stop_alarm_video_recording(app, alarm_id):
    with _recorders_lock:
        recorder = _recorders.get(id(app))
    if recorder is None:
        return False
    return recorder.stop_recording(alarm_id)
