import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class LivenessDetector:
    """
    Lightweight Liveness Detector to identify photo/video playback spoofing attacks.
    Uses Laplacian variance for blurriness analysis and HSV color distribution verification.
    """
    def __init__(self, blur_threshold=80.0):
        self.blur_threshold = blur_threshold

    def is_live(self, face_crop) -> tuple[bool, float]:
        """
        Evaluate if a face crop is live or a spoofing attempt.
        Returns: (is_live, confidence)
        """
        if face_crop is None or face_crop.size == 0:
            return False, 0.0

        try:
            # 1. Blurriness Check (Laplacian Variance)
            # Replayed video screens or printouts usually have lower variance of Laplacian due to screen resolution limits
            # or camera refocusing blur.
            gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

            # 2. Color Saturation & Value Variance Check
            # Digital screen playbacks and prints on paper generally exhibit lower variance in color saturation
            # or unnatural peaks in H/S/V channels.
            hsv = cv2.cvtColor(face_crop, cv2.COLOR_BGR2HSV)
            h, s, v = cv2.split(hsv)
            std_s = np.std(s)
            std_v = np.std(v)

            is_live_flag = True
            score = 1.0

            # Heuristics:
            # If the image is extremely blurry, it's highly likely a physical photo printed on paper or a low-res screen.
            if laplacian_var < self.blur_threshold:
                is_live_flag = False
                score = float(laplacian_var / self.blur_threshold)
            # Flat prints usually have very uniform color saturation compared to a 3D human face
            elif std_s < 8.0 or std_v < 12.0:
                is_live_flag = False
                score = 0.3
            else:
                # Combined confidence score based on Laplacian variance
                score = min(1.0, float(laplacian_var / 250.0))

            return is_live_flag, score

        except Exception as e:
            logger.error(f"Error in liveness detection algorithm: {e}")
            return True, 1.0  # Safe default on error
