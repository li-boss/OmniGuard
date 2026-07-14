import logging
import numpy as np
import cv2
import time

logger = logging.getLogger(__name__)

try:
    import mediapipe as mp
    from mediapipe.tasks import python
    from mediapipe.tasks.python import vision
    MEDIAPIPE_AVAILABLE = True
except ImportError as e:
    MEDIAPIPE_AVAILABLE = False
    logger.warning(f"MediaPipe not installed or import failed: {e}. Fall detection will be disabled.")


class FallDetector:
    def __init__(self, 
                 angle_threshold=30,
                 hip_height_threshold=0.5,
                 confidence_threshold=0.5):
        if not MEDIAPIPE_AVAILABLE:
            raise ImportError("MediaPipe is required for fall detection")
        
        self.angle_threshold = angle_threshold
        self.hip_height_threshold = hip_height_threshold
        self.confidence_threshold = confidence_threshold
        
        model_path = self._get_pose_model()
        
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.5,
            min_pose_presence_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.pose = vision.PoseLandmarker.create_from_options(options)
        self.timestamp = 0
        
        logger.info("FallDetector initialized with MediaPipe Task API")
    
    def _get_pose_model(self):
        import os
        from pathlib import Path
        import urllib.request
        
        model_dir = Path(__file__).parent / 'weights'
        model_dir.mkdir(exist_ok=True)
        model_path = model_dir / 'pose_landmarker_lite.task'
        
        if not model_path.exists():
            url = 'https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task'
            logger.info(f"Downloading pose model from {url}...")
            try:
                urllib.request.urlretrieve(url, str(model_path))
                logger.info(f"Pose model downloaded to {model_path}")
            except Exception as e:
                logger.error(f"Failed to download pose model: {e}")
                raise
        
        return str(model_path)
    
    def detect(self, frame, bbox=None):
        if frame is None:
            return None
        
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            if bbox is not None:
                x, y, w, h = bbox
                x = max(0, int(x))
                y = max(0, int(y))
                w = min(w, frame.shape[1] - x)
                h = min(h, frame.shape[0] - y)
                if w > 0 and h > 0:
                    rgb_frame = rgb_frame[y:y+h, x:x+w]
            
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            
            self.timestamp += 1
            detection_result = self.pose.detect(mp_image)
            
            if not detection_result.pose_landmarks or len(detection_result.pose_landmarks) == 0:
                return None
            
            landmarks = detection_result.pose_landmarks[0]
            
            fall_detected, confidence, details = self._analyze_pose(landmarks)
            
            return {
                'fall_detected': fall_detected,
                'confidence': confidence,
                'details': details,
                'landmarks': landmarks
            }
            
        except Exception as e:
            logger.error(f"Error in fall detection: {e}")
            return None
    
    def _analyze_pose(self, landmarks):
        LEFT_SHOULDER = 11
        RIGHT_SHOULDER = 12
        LEFT_HIP = 23
        RIGHT_HIP = 24
        LEFT_KNEE = 25
        RIGHT_KNEE = 26
        LEFT_ANKLE = 27
        RIGHT_ANKLE = 28
        
        MIN_VISIBILITY = 0.5
        
        left_shoulder = landmarks[LEFT_SHOULDER]
        right_shoulder = landmarks[RIGHT_SHOULDER]
        left_hip = landmarks[LEFT_HIP]
        right_hip = landmarks[RIGHT_HIP]
        left_knee = landmarks[LEFT_KNEE]
        right_knee = landmarks[RIGHT_KNEE]
        left_ankle = landmarks[LEFT_ANKLE]
        right_ankle = landmarks[RIGHT_ANKLE]
        
        required_keypoints = [
            left_shoulder, right_shoulder,
            left_hip, right_hip,
            left_knee, right_knee,
            left_ankle, right_ankle
        ]
        
        for kp in required_keypoints:
            if kp.visibility < MIN_VISIBILITY:
                logger.debug(f"Keypoint visibility too low: {kp.visibility:.2f}, skipping fall detection")
                return False, 0.0, {'reason': 'incomplete_body', 'visibility': kp.visibility}
        
        shoulder_mid = self._get_midpoint(left_shoulder, right_shoulder)
        hip_mid = self._get_midpoint(left_hip, right_hip)
        
        body_angle = self._calculate_angle_from_vertical(shoulder_mid, hip_mid)
        
        hip_height = hip_mid.y
        ankle_avg_y = (left_ankle.y + right_ankle.y) / 2
        relative_hip_height = ankle_avg_y - hip_height
        
        visibility = min(
            left_shoulder.visibility, right_shoulder.visibility,
            left_hip.visibility, right_hip.visibility,
            left_knee.visibility, right_knee.visibility,
            left_ankle.visibility, right_ankle.visibility
        )
        
        fall_indicators = []
        
        if body_angle > self.angle_threshold:
            fall_indicators.append('body_tilt')
        
        if relative_hip_height < self.hip_height_threshold:
            fall_indicators.append('low_hip')
        
        knee_left_angle = self._calculate_angle(left_hip, left_knee, left_ankle)
        knee_right_angle = self._calculate_angle(right_hip, right_knee, right_ankle)
        avg_knee_angle = (knee_left_angle + knee_right_angle) / 2
        if avg_knee_angle < 120:
            fall_indicators.append('bent_knees')
        
        shoulder_width = abs(right_shoulder.x - left_shoulder.x)
        hip_width = abs(right_hip.x - left_hip.x)
        if shoulder_width > 0 and hip_width > 0:
            width_ratio = shoulder_width / hip_width
            if width_ratio > 1.5 or width_ratio < 0.67:
                fall_indicators.append('unusual_proportions')
        
        fall_detected = len(fall_indicators) >= 1
        confidence = visibility if fall_detected else 0.0
        
        details = {
            'body_angle': body_angle,
            'relative_hip_height': relative_hip_height,
            'knee_angle': avg_knee_angle,
            'fall_indicators': fall_indicators,
            'visibility': visibility,
            'complete_body': True
        }
        
        return fall_detected, confidence, details
    
    def _calculate_angle(self, point1, point2, point3):
        v1 = np.array([point1.x - point2.x, point1.y - point2.y])
        v2 = np.array([point3.x - point2.x, point3.y - point2.y])
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.degrees(np.arccos(cos_angle))
        
        return angle
    
    def _get_midpoint(self, point1, point2):
        return type('obj', (object,), {
            'x': (point1.x + point2.x) / 2,
            'y': (point1.y + point2.y) / 2,
            'z': (point1.z + point2.z) / 2
        })()
    
    def _calculate_angle_from_vertical(self, point1, point2):
        dx = point2.x - point1.x
        dy = point2.y - point1.y
        
        if dy == 0:
            return 90.0
        
        angle_rad = np.arctan(abs(dx) / abs(dy))
        angle_deg = np.degrees(angle_rad)
        
        return angle_deg
    
    def close(self):
        if hasattr(self, 'pose'):
            self.pose.close()
        logger.info("FallDetector closed")
