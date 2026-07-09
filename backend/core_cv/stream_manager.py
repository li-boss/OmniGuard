import cv2
import time
import logging

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

    def connect(self):
        self.last_retry_time = time.time()
        if self.capture is not None:
            try:
                self.capture.release()
            except Exception:
                pass
        
        logger.info(f"Connecting to video stream: {self.url} ...")
        try:
            url_str = str(self.url)
            if url_str.isdigit():
                camera_idx = int(self.url)
                # Try DirectShow first on Windows
                self.capture = cv2.VideoCapture(camera_idx, cv2.CAP_DSHOW)
                if not self.capture.isOpened():
                    self.capture = cv2.VideoCapture(camera_idx)
                
                # If camera 0 failed, try camera 1 as fallback
                if not self.capture.isOpened() and camera_idx == 0:
                    logger.info("Camera 0 failed to open. Trying Camera 1 as fallback...")
                    self.capture = cv2.VideoCapture(1, cv2.CAP_DSHOW)
                    if not self.capture.isOpened():
                        self.capture = cv2.VideoCapture(1)
            else:
                self.capture = cv2.VideoCapture(self.url)

            # Set buffer size to 1 to get latest frames
            if self.capture.isOpened():
                self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            if self.capture.isOpened():
                self.connected = True
                self.consecutive_failures = 0
                logger.info(f"Successfully connected to stream: {self.url}")
                return True
            else:
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
        # 1. Check connectivity and retry cooldown
        if not self.connected or self.capture is None or not self.capture.isOpened():
            now = time.time()
            # Calculate backoff cooldown: 1s, 2s, 4s, 8s, up to 10s max
            cooldown = min(10.0, 1.0 * (2 ** min(max(0, self.consecutive_failures - 1), 3)))
            if now - self.last_retry_time < cooldown:
                # Still in cooldown, skip to prevent blocking the round-robin loop
                return None
            
            # Cooldown passed, try to reconnect
            if not self.connect():
                return None

        # 2. Frame-skipping index check
        self.index += 1
        skip_frame = (self.index % self.frame_skip != 0)

        # 3. Non-blocking frame flushing (Get-Latest-Frame strategy)
        # We grab all buffered frames, keeping only the last one
        last_frame = None
        grabbed_any = False
        
        start_time = time.time()
        # Calculate actual timeout based on failures (fast fail)
        actual_timeout_ms = base_timeout_ms // (2 ** min(self.consecutive_failures, 3))
        timeout_seconds = actual_timeout_ms / 1000.0

        try:
            while True:
                # check if timeout exceeded
                if time.time() - start_time > timeout_seconds:
                    break
                
                # Grab frame (very fast, doesn't decode)
                grabbed = self.capture.grab()
                if not grabbed:
                    break
                grabbed_any = True
                
                # If we need to skip this frame or if there are more frames in the buffer,
                # we don't retrieve/decode it yet.
                # However, to be safe, if we grabbed a frame, we can keep track that a frame is available.

            if grabbed_any:
                # We got at least one frame. Decode the latest grabbed frame.
                ok, frame = self.capture.retrieve()
                if ok and frame is not None:
                    self.consecutive_failures = 0
                    self.connected = True
                    # If we need to skip processing this frame, return None (but we cleared failures)
                    if skip_frame:
                        return None
                    return frame
                else:
                    logger.warning(f"Grabbed frame but failed to retrieve for {self.url}")
            
            # If we reached here without returning a frame, count as a failure
            self.consecutive_failures += 1
            if self.consecutive_failures > 5:
                # Mark as disconnected after 5 failures to trigger reconnect
                self.connected = False
                logger.error(f"Stream {self.url} disconnected due to consecutive retrieval failures")
            return None

        except Exception as e:
            logger.error(f"Error reading frame from stream {self.url}: {e}")
            self.consecutive_failures += 1
            self.connected = False
            return None

    def read(self):
        # Keep original read method signature for backward compatibility
        return self.get_latest_frame()

    def release(self):
        self.connected = False
        if self.capture is not None:
            try:
                self.capture.release()
                logger.info(f"Released video capture for {self.url}")
            except Exception as e:
                logger.error(f"Error releasing video capture for {self.url}: {e}")
            self.capture = None
