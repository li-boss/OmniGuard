import os
import time
import logging
import threading
import subprocess
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class RtmpPusher:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        with self._lock:
            if self._initialized:
                return
            self.running = False
            self.cap_thread = None
            self.push_thread = None
            self.cap = None
            self.proc = None
            self.rtmp_url = "rtmp://39.97.236.134:9090/live/cam01"
            self.camera_index = int(os.getenv("CAMERA_INDEX", "0"))
            self.active_camera_index = None
            self.active_backend = None
            self.last_error = None
            self.latest_frame = None
            self.frame_lock = threading.Lock()
            self.enable_rtmp_push = os.getenv("ENABLE_RTMP_PUSH", "false").lower() in ("1", "true", "yes")
            self._initialized = True

    def start(self):
        with self._lock:
            if self.running:
                logger.warning("RTMP Pusher is already running.")
                return
            self.running = True
            self.cap_thread = threading.Thread(target=self._capture_loop, name="RtmpPusher-CapThread", daemon=True)
            self.cap_thread.start()
            if self.enable_rtmp_push:
                self.push_thread = threading.Thread(target=self._push_loop, name="RtmpPusher-PushThread", daemon=True)
                self.push_thread.start()
                logger.info(f"Local camera capture started; RTMP push enabled: {self.rtmp_url}")
            else:
                logger.info("Local camera capture started; remote RTMP push is disabled")

    def stop(self):
        with self._lock:
            if not self.running:
                return
            self.running = False
            logger.info("Stopping RTMP Pusher...")
        
        if self.cap_thread:
            self.cap_thread.join(timeout=3.0)
            self.cap_thread = None
        
        if self.push_thread:
            self.push_thread.join(timeout=3.0)
            self.push_thread = None
        
        self._cleanup()
        logger.info("RTMP Pusher stopped successfully.")

    def get_latest_frame(self):
        with self.frame_lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def get_status(self):
        with self._lock:
            running = self.running
            active_camera_index = self.active_camera_index
            active_backend = self.active_backend
            last_error = self.last_error
        with self.frame_lock:
            has_frame = self.latest_frame is not None
        return {
            "running": running,
            "connected": has_frame,
            "configured_camera_index": self.camera_index,
            "active_camera_index": active_camera_index,
            "backend": active_backend,
            "last_error": last_error,
        }

    @staticmethod
    def _frame_is_usable(frame):
        """Reject empty and effectively black frames returned by virtual/privacy cameras."""
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return False
        if frame.ndim != 3 or frame.shape[2] < 3:
            return False
        # Sampling keeps this check cheap enough to run continuously. A genuinely
        # dark scene still has sensor noise; an all-zero privacy frame does not.
        sample = frame[::16, ::16, :3]
        return bool(np.max(sample) > 4 or np.std(sample) > 1.0)

    def _camera_candidates(self):
        candidates = [self.camera_index]
        for index in range(4):
            if index not in candidates:
                candidates.append(index)
        return candidates

    def _open_camera(self):
        """Open a Windows camera using the first backend that returns frames."""
        backends = []
        if os.name == "nt":
            # DirectShow is substantially more reliable than MSMF on many USB
            # and integrated webcams, so try it first.
            backends.append(("DirectShow", cv2.CAP_DSHOW))
        backends.append(("Default", cv2.CAP_ANY))
        if os.name == "nt":
            backends.append(("MSMF", cv2.CAP_MSMF))

        for camera_index in self._camera_candidates():
            for backend_name, backend in backends:
                cap = cv2.VideoCapture(camera_index, backend)
                if not cap.isOpened():
                    cap.release()
                    continue

                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                cap.set(cv2.CAP_PROP_FPS, 30)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

                for _ in range(20):
                    ok, frame = cap.read()
                    if ok and self._frame_is_usable(frame):
                        with self.frame_lock:
                            self.latest_frame = frame.copy()
                        with self._lock:
                            self.active_camera_index = camera_index
                            self.active_backend = backend_name
                            self.last_error = None
                        logger.info(f"Opened local camera {camera_index} using {backend_name}")
                        return cap
                    time.sleep(0.05)
                logger.warning(
                    f"Camera {camera_index} using {backend_name} returned no usable frames"
                )
                cap.release()
        with self._lock:
            self.active_camera_index = None
            self.active_backend = None
            self.last_error = (
                "No usable camera frames. Check the privacy shutter, Windows camera "
                "permission, or close other applications using the camera."
            )
        return None

    def _cleanup(self):
        with self._lock:
            cap = self.cap
            self.cap = None
            proc = self.proc
            self.proc = None

        if cap:
            try:
                cap.release()
            except Exception as e:
                logger.error(f"Error releasing camera in RTMP Pusher: {e}")
        
        if proc:
            try:
                proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception as e:
                logger.error(f"Error terminating FFmpeg in RTMP Pusher: {e}")

    def _capture_loop(self):
        while self.running:
            logger.info(f"RTMP Pusher capture thread connecting to camera {self.camera_index}...")
            cap = self._open_camera()
            if cap is None:
                logger.error(f"RTMP Pusher failed to open camera {self.camera_index}. Retrying in 5 seconds...")
                time.sleep(5.0)
                continue

            with self._lock:
                self.cap = cap

            logger.info("RTMP Pusher capture thread successfully opened camera.")

            unusable_frames = 0
            while self.running:
                ok, frame = cap.read()
                if not ok or not self._frame_is_usable(frame):
                    unusable_frames += 1
                    if unusable_frames >= 20:
                        logger.warning("Local camera returned 20 unusable/black frames; reconnecting.")
                        with self._lock:
                            self.last_error = "Camera is returning black or invalid frames."
                        break
                    time.sleep(0.03)
                    continue

                unusable_frames = 0

                with self.frame_lock:
                    self.latest_frame = frame.copy()

                time.sleep(0.001)

            with self._lock:
                if self.cap == cap:
                    self.cap = None
            cap.release()
            with self.frame_lock:
                self.latest_frame = None
            with self._lock:
                self.active_camera_index = None
                self.active_backend = None
            logger.warning("RTMP Pusher capture connection lost. Reconnecting in 3 seconds...")
            time.sleep(3.0)

    def _push_loop(self):
        while self.running:
            frame = None
            while self.running and frame is None:
                with self.frame_lock:
                    if self.latest_frame is not None:
                        frame = self.latest_frame.copy()
                if frame is None:
                    time.sleep(0.1)

            if not self.running:
                break

            h, w = frame.shape[:2]
            logger.info(f"Starting FFmpeg process in RTMP Pusher. Resolution: {w}x{h}")

            ffmpeg_cmd = [
                'ffmpeg',
                '-y',
                '-f', 'rawvideo',
                '-vcodec', 'rawvideo',
                '-pix_fmt', 'bgr24',
                '-s', f"{w}x{h}",
                '-r', '25',
                '-i', '-',
                '-c:v', 'libx264',
                '-pix_fmt', 'yuv420p',
                '-preset', 'ultrafast',
                '-tune', 'zerolatency',
                '-rw_timeout', '3000000',
                '-f', 'flv',
                self.rtmp_url
            ]

            proc = None
            try:
                proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
            except Exception as e:
                logger.error(f"RTMP Pusher failed to start FFmpeg subprocess: {e}")
                time.sleep(5.0)
                continue

            with self._lock:
                self.proc = proc

            last_push_time = 0.0
            while self.running:
                if proc.poll() is not None:
                    logger.warning("FFmpeg process exited prematurely.")
                    break

                with self.frame_lock:
                    current_frame = self.latest_frame.copy() if self.latest_frame is not None else None

                if current_frame is not None:
                    now = time.time()
                    if now - last_push_time >= 0.04:  # ~25 fps limit
                        try:
                            proc.stdin.write(current_frame.tobytes())
                            proc.stdin.flush()
                            last_push_time = now
                        except Exception as e:
                            logger.error(f"RTMP Pusher write to FFmpeg stdin failed: {e}")
                            break

                time.sleep(0.005)

            with self._lock:
                if self.proc == proc:
                    self.proc = None
            
            try:
                proc.stdin.close()
                proc.terminate()
                proc.wait(timeout=2.0)
            except Exception:
                pass

            logger.warning("RTMP Pusher push connection lost. Restarting FFmpeg in 3 seconds...")
            time.sleep(3.0)

# Global singleton helper
rtmp_pusher_svc = RtmpPusher()
