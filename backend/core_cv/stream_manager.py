import cv2
import time
import logging
import threading
import numpy as np

logger = logging.getLogger(__name__)


class StreamManager:
    def __init__(self, url, frame_skip=2):
        self.url = url
        self.frame_skip = frame_skip
        self.capture = None
        self.index = 0
        self.consecutive_failures = 0
        self.last_retry_time = 0.0
        self.connected = False
        self._lock = threading.RLock()
        self._local_backend_index = 0

    def _is_local_camera(self):
        return str(self.url).isdigit()

    def _local_backends(self):
        # CAP_ANY matches backend/test_camera.py and is usually the most stable
        # option for Windows webcams. MSMF/DSHOW remain fallback options.
        candidates = [cv2.CAP_ANY]
        for backend_name in ("CAP_MSMF", "CAP_DSHOW"):
            backend = getattr(cv2, backend_name, None)
            if backend is not None and backend not in candidates:
                candidates.append(backend)
        return candidates

    def _configure_capture(self, capture):
        try:
            capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            capture.set(cv2.CAP_PROP_FPS, 25)
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        except Exception as e:
            logger.debug(f"Unable to configure capture properties for {self.url}: {e}")

    def _looks_corrupt_frame(self, frame):
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return True
        if frame.dtype != np.uint8 or len(frame.shape) != 3 or frame.shape[2] not in (3, 4):
            return True

        h, w = frame.shape[:2]
        if h < 32 or w < 32:
            return True

        step_y = max(1, h // 180)
        step_x = max(1, w // 240)
        sample = frame[::step_y, ::step_x, :3]
        horizontal_diff = np.mean(np.abs(sample[:, 1:].astype(np.int16) - sample[:, :-1].astype(np.int16)))
        vertical_diff = np.mean(np.abs(sample[1:, :].astype(np.int16) - sample[:-1, :].astype(np.int16)))
        channel_std = float(np.mean(np.std(sample, axis=(0, 1))))

        # Full-frame colored static has both high color variance and high
        # neighboring-pixel differences. Normal camera frames rarely hit both.
        return channel_std > 55.0 and max(horizontal_diff, vertical_diff) > 55.0

    def _read_valid_warmup_frame(self, capture, attempts=8):
        frame = None
        for _ in range(attempts):
            ok, candidate = capture.read()
            if ok and candidate is not None:
                frame = candidate
                if not self._looks_corrupt_frame(candidate):
                    return candidate
            time.sleep(0.03)
        return None if self._looks_corrupt_frame(frame) else frame

    def _open_local_capture(self, camera_idx):
        backends = self._local_backends()
        start = self._local_backend_index % len(backends)
        ordered_backends = backends[start:] + backends[:start]

        for backend in ordered_backends:
            capture = cv2.VideoCapture(camera_idx, backend)
            if not capture.isOpened():
                capture.release()
                continue

            self._configure_capture(capture)
            warmup_frame = self._read_valid_warmup_frame(capture)
            if warmup_frame is not None:
                self._local_backend_index = backends.index(backend)
                logger.info(f"Opened local camera {camera_idx} with backend {backend}")
                return capture

            logger.warning(
                f"Local camera {camera_idx} opened with backend {backend}, "
                "but frames look corrupt. Trying next backend."
            )
            capture.release()

        return None

    def connect(self):
        with self._lock:
            self.last_retry_time = time.time()
            if self.capture is not None:
                try:
                    self.capture.release()
                except Exception:
                    pass
                self.capture = None

            logger.info(f"Connecting to video stream: {self.url} ...")
            try:
                if self._is_local_camera():
                    camera_idx = int(self.url)
                    self.capture = self._open_local_capture(camera_idx)

                    if self.capture is None and camera_idx == 0:
                        logger.info("Camera 0 failed to open cleanly. Trying Camera 1 as fallback...")
                        self.capture = self._open_local_capture(1)
                else:
                    self.capture = cv2.VideoCapture(self.url)
                    if self.capture.isOpened():
                        self._configure_capture(self.capture)

                if self.capture is not None and self.capture.isOpened():
                    self.connected = True
                    self.consecutive_failures = 0
                    logger.info(f"Successfully connected to stream: {self.url}")
                    return True

                self.connected = False
                self.consecutive_failures += 1
                logger.error(f"Failed to open video capture for {self.url}")
                return False
            except Exception as e:
                self.connected = False
                self.consecutive_failures += 1
                logger.error(f"Exception while connecting to {self.url}: {e}")
                return False

    def get_latest_frame(self, base_timeout_ms=1000):
        with self._lock:
            if not self.connected or self.capture is None or not self.capture.isOpened():
                now = time.time()
                cooldown = min(10.0, 1.0 * (2 ** min(max(0, self.consecutive_failures - 1), 3)))
                if now - self.last_retry_time < cooldown:
                    return None
                if not self.connect():
                    return None

            self.index += 1
            skip_frame = self.index % self.frame_skip != 0

            if self._is_local_camera():
                return self._read_local_frame(skip_frame)

            return self._read_network_frame(skip_frame, base_timeout_ms)

    def _read_local_frame(self, skip_frame):
        try:
            ok, frame = self.capture.read()
            if ok and frame is not None and not self._looks_corrupt_frame(frame):
                self.consecutive_failures = 0
                self.connected = True
                if skip_frame:
                    return None
                return np.ascontiguousarray(frame[:, :, :3])

            self.consecutive_failures += 1
            if ok and frame is not None:
                logger.warning(f"Discarded corrupt-looking frame from local camera {self.url}")
                self._local_backend_index += 1
            if self.consecutive_failures > 3:
                self.connected = False
                logger.error(f"Stream {self.url} disconnected due to consecutive invalid frames")
            return None
        except Exception as e:
            logger.error(f"Error reading frame from local camera {self.url}: {e}")
            self.consecutive_failures += 1
            self.connected = False
            return None

    def _read_network_frame(self, skip_frame, base_timeout_ms):
        grabbed_any = False
        start_time = time.time()
        actual_timeout_ms = base_timeout_ms // (2 ** min(self.consecutive_failures, 3))
        timeout_seconds = actual_timeout_ms / 1000.0

        try:
            while True:
                if time.time() - start_time > timeout_seconds:
                    break
                grabbed = self.capture.grab()
                if not grabbed:
                    break
                grabbed_any = True

            if grabbed_any:
                ok, frame = self.capture.retrieve()
                if ok and frame is not None:
                    self.consecutive_failures = 0
                    self.connected = True
                    if skip_frame:
                        return None
                    return np.ascontiguousarray(frame[:, :, :3])
                logger.warning(f"Grabbed frame but failed to retrieve for {self.url}")

            self.consecutive_failures += 1
            if self.consecutive_failures > 5:
                self.connected = False
                logger.error(f"Stream {self.url} disconnected due to consecutive retrieval failures")
            return None
        except Exception as e:
            logger.error(f"Error reading frame from stream {self.url}: {e}")
            self.consecutive_failures += 1
            self.connected = False
            return None

    def read(self):
        return self.get_latest_frame()

    def release(self):
        with self._lock:
            self.connected = False
            if self.capture is not None:
                try:
                    self.capture.release()
                    logger.info(f"Released video capture for {self.url}")
                except Exception as e:
                    logger.error(f"Error releasing video capture for {self.url}: {e}")
                self.capture = None