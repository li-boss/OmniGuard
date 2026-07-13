import os
import cv2
import time
import logging
import threading
import numpy as np

# Disable FFmpeg buffering globally in OpenCV for lowest latency RTMP/RTSP streams
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "fflags;nobuffer"

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
        
        # Async reader thread state
        self.latest_frame = None
        self.running = False
        self.thread = None

    def _is_local_camera(self):
        return str(self.url).isdigit()

    def _local_backends(self):
        # Prefer the backend that can open the integrated camera reliably on
        # Windows. CAP_ANY remains the final fallback.
        candidates = []
        for backend_name in ("CAP_DSHOW", "CAP_MSMF", "CAP_ANY"):
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

        return False

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

    def start(self):
        if self._is_local_camera():
            # No background thread needed for local cameras!
            # Frames are read directly from rtmp_pusher_svc
            self.running = True
            return

        with self._lock:
            if self.running:
                return
            self.running = True
            self.thread = threading.Thread(target=self._run_loop, name=f"StreamReader-{self.url}", daemon=True)
            self.thread.start()
            logger.info(f"Started background stream reader thread for {self.url}")

    def stop(self):
        with self._lock:
            self.running = False
        if self.thread:
            self.thread.join(timeout=2.0)
            self.thread = None

    def _run_loop(self):
        while self.running:
            # 1. Connect if not connected
            is_connected = False
            with self._lock:
                is_connected = self.connected and self.capture is not None and self.capture.isOpened()

            if not is_connected:
                # Cooldown logic
                now = time.time()
                with self._lock:
                    failures = self.consecutive_failures
                cooldown = min(10.0, 1.0 * (2 ** min(max(0, failures - 1), 3)))
                if now - self.last_retry_time < cooldown:
                    time.sleep(0.1)
                    continue

                self.connect()  # This blocks but ONLY in this background thread!
                if not self.connected:
                    time.sleep(0.1)
                    continue

            # 2. Read frame
            self.index += 1
            skip_frame = self.index % self.frame_skip != 0

            frame = None
            if self._is_local_camera():
                frame = self._read_local_frame(skip_frame)
            else:
                frame = self._read_network_frame(skip_frame, base_timeout_ms=1000)

            if frame is not None:
                with self._lock:
                    self.latest_frame = frame
            
            # Short sleep to prevent CPU hogging and yield to other threads
            time.sleep(0.005)

    def connect(self):
        # 1. Clear old capture under lock
        with self._lock:
            self.last_retry_time = time.time()
            old_cap = self.capture
            self.capture = None

        if old_cap is not None:
            try:
                old_cap.release()
            except Exception:
                pass

        logger.info(f"Connecting to video stream: {self.url} ...")

        new_capture = None
        try:
            if self._is_local_camera():
                self.connected = True
                self.consecutive_failures = 0
                logger.info(f"Local camera mode active via RtmpPusher shared frames.")
                return True
            else:
                new_capture = cv2.VideoCapture(self.url)
                if new_capture.isOpened():
                    self._configure_capture(new_capture)

            # 2. Assign new capture under lock
            with self._lock:
                if new_capture is not None and new_capture.isOpened():
                    self.capture = new_capture
                    self.connected = True
                    self.consecutive_failures = 0
                    logger.info(f"Successfully connected to stream: {self.url}")
                    return True
                else:
                    if new_capture is not None:
                        try:
                            new_capture.release()
                        except Exception:
                            pass
                    self.connected = False
                    self.consecutive_failures += 1
                    logger.error(f"Failed to open video capture for {self.url}")
                    return False
        except Exception as e:
            if new_capture is not None:
                try:
                    new_capture.release()
                except Exception:
                    pass
            with self._lock:
                self.connected = False
                self.consecutive_failures += 1
                logger.error(f"Exception while connecting to {self.url}: {e}")
                return False

    def get_latest_frame(self, base_timeout_ms=1000):
        if self._is_local_camera():
            from services.rtmp_pusher import rtmp_pusher_svc
            return rtmp_pusher_svc.get_latest_frame()

        # Automatically start the background thread if it is not running
        if not self.running:
            self.start()

        # Wait a tiny bit (up to 100ms) if latest_frame is None and we are connected
        start_time = time.time()
        while self.running and time.time() - start_time < 0.1:
            with self._lock:
                if self.latest_frame is not None:
                    break
                is_connected = self.connected
            if not is_connected:
                break
            time.sleep(0.005)

        with self._lock:
            frame = self.latest_frame
            self.latest_frame = None  # Clear so we don't consume the same frame twice
            return frame

    def _read_local_frame(self, skip_frame):
        try:
            from services.rtmp_pusher import rtmp_pusher_svc
            frame = rtmp_pusher_svc.get_latest_frame()
            if frame is not None:
                with self._lock:
                    self.consecutive_failures = 0
                    self.connected = True
                if skip_frame:
                    return None
                return np.ascontiguousarray(frame[:, :, :3])

            # If no frame is available yet from the pusher service, do a short wait
            time.sleep(0.01)
            return None
        except Exception as e:
            logger.error(f"Error reading shared frame from RtmpPusher: {e}")
            return None

    def _read_network_frame(self, skip_frame, base_timeout_ms):
        with self._lock:
            cap = self.capture
        if cap is None:
            return None
        grabbed_any = False
        start_time = time.time()
        with self._lock:
            failures = self.consecutive_failures
        actual_timeout_ms = base_timeout_ms // (2 ** min(failures, 3))
        timeout_seconds = actual_timeout_ms / 1000.0

        try:
            while True:
                if time.time() - start_time > timeout_seconds:
                    break
                grabbed = cap.grab()
                if not grabbed:
                    break
                grabbed_any = True

            if grabbed_any:
                ok, frame = cap.retrieve()
                if ok and frame is not None:
                    with self._lock:
                        self.consecutive_failures = 0
                        self.connected = True
                    if skip_frame:
                        return None
                    return np.ascontiguousarray(frame[:, :, :3])
                logger.warning(f"Grabbed frame but failed to retrieve for {self.url}")

            with self._lock:
                self.consecutive_failures += 1
                if self.consecutive_failures > 5:
                    self.connected = False
                    logger.error(f"Stream {self.url} disconnected due to consecutive retrieval failures")
            return None
        except Exception as e:
            logger.error(f"Error reading frame from stream {self.url}: {e}")
            with self._lock:
                self.consecutive_failures += 1
                self.connected = False
            return None

    def read(self):
        return self.get_latest_frame()

    def release(self):
        self.stop()
        with self._lock:
            self.connected = False
            if self.capture is not None:
                try:
                    self.capture.release()
                    logger.info(f"Released video capture for {self.url}")
                except Exception as e:
                    logger.error(f"Error releasing video capture for {self.url}: {e}")
                self.capture = None
