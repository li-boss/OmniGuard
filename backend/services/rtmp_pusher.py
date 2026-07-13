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
            self.camera_index = 0
            self.latest_frame = None
            self.frame_lock = threading.Lock()
            self._initialized = True

    def start(self):
        with self._lock:
            if self.running:
                logger.warning("RTMP Pusher is already running.")
                return
            self.running = True
            self.cap_thread = threading.Thread(target=self._capture_loop, name="RtmpPusher-CapThread", daemon=True)
            self.push_thread = threading.Thread(target=self._push_loop, name="RtmpPusher-PushThread", daemon=True)
            self.cap_thread.start()
            self.push_thread.start()
            logger.info(f"RTMP Pusher started: pushing camera {self.camera_index} to {self.rtmp_url}")

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
            return self.latest_frame

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
            cap = cv2.VideoCapture(self.camera_index)
            if not cap.isOpened():
                logger.error(f"RTMP Pusher failed to open camera {self.camera_index}. Retrying in 5 seconds...")
                cap.release()
                time.sleep(5.0)
                continue

            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            cap.set(cv2.CAP_PROP_FPS, 30)

            with self._lock:
                self.cap = cap

            logger.info("RTMP Pusher capture thread successfully opened camera.")

            while self.running:
                ok, frame = cap.read()
                if not ok or frame is None:
                    logger.warning("RTMP Pusher failed to read frame from camera.")
                    break

                with self.frame_lock:
                    self.latest_frame = frame.copy()

                time.sleep(0.001)

            with self._lock:
                if self.cap == cap:
                    self.cap = None
            cap.release()
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
