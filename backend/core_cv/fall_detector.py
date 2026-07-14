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
                x1, y1, x2, y2 = (int(value) for value in bbox)
                frame_height, frame_width = frame.shape[:2]
                x1 = max(0, min(frame_width, x1))
                y1 = max(0, min(frame_height, y1))
                x2 = max(0, min(frame_width, x2))
                y2 = max(0, min(frame_height, y2))
                if x2 <= x1 or y2 <= y1:
                    return None
                rgb_frame = rgb_frame[y1:y2, x1:x2]
            
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
        
        required_keypoints = {
            'left_shoulder': left_shoulder,
            'right_shoulder': right_shoulder,
            'left_hip': left_hip,
            'right_hip': right_hip,
            'left_knee': left_knee,
            'right_knee': right_knee,
            'left_ankle': left_ankle,
            'right_ankle': right_ankle,
        }
        visible_keypoints = {
            name: point
            for name, point in required_keypoints.items()
            if point.visibility >= MIN_VISIBILITY
        }
        visible_points = len(visible_keypoints)
        visible_shoulders = [
            point for point in (left_shoulder, right_shoulder)
            if point.visibility >= MIN_VISIBILITY
        ]
        visible_hips = [
            point for point in (left_hip, right_hip)
            if point.visibility >= MIN_VISIBILITY
        ]

        if visible_points < 6 or not visible_shoulders or not visible_hips:
            logger.debug("Insufficient pose landmarks: %s/8 visible", visible_points)
            return False, 0.0, {
                'reason': 'incomplete_body',
                'visible_points': visible_points,
                'required_visible_points': 6,
                'fall_indicators': [],
                'complete_body': False,
            }

        shoulder_mid = self._get_average_point(visible_shoulders)
        hip_mid = self._get_average_point(visible_hips)
        
        body_angle = self._calculate_angle_from_vertical(shoulder_mid, hip_mid)
        
        hip_height = hip_mid.y
        visible_ankles = [
            point for point in (left_ankle, right_ankle)
            if point.visibility >= MIN_VISIBILITY
        ]
        relative_hip_height = None
        if visible_ankles:
            ankle_avg_y = sum(point.y for point in visible_ankles) / len(visible_ankles)
            relative_hip_height = ankle_avg_y - hip_height

        visibility = min(point.visibility for point in visible_keypoints.values())
        
        fall_indicators = []
        
        if body_angle > self.angle_threshold:
            fall_indicators.append('body_tilt')

        if body_angle > 60:
            fall_indicators.append('horizontal_body')

        if relative_hip_height is not None and relative_hip_height < self.hip_height_threshold:
            fall_indicators.append('low_hip')
        
        knee_angles = []
        if all(name in visible_keypoints for name in ('left_hip', 'left_knee', 'left_ankle')):
            knee_angles.append(self._calculate_angle(left_hip, left_knee, left_ankle))
        if all(name in visible_keypoints for name in ('right_hip', 'right_knee', 'right_ankle')):
            knee_angles.append(self._calculate_angle(right_hip, right_knee, right_ankle))
        avg_knee_angle = sum(knee_angles) / len(knee_angles) if knee_angles else None
        if avg_knee_angle is not None and avg_knee_angle < 120:
            fall_indicators.append('bent_knees')
        
        shoulder_hip_ratio = None
        if all(name in visible_keypoints for name in ('left_shoulder', 'right_shoulder', 'left_hip', 'right_hip')):
            shoulder_width = abs(right_shoulder.x - left_shoulder.x)
            hip_width = abs(right_hip.x - left_hip.x)
            if shoulder_width > 0 and hip_width > 0:
                shoulder_hip_ratio = shoulder_width / hip_width
            if shoulder_hip_ratio is not None and (shoulder_hip_ratio > 1.5 or shoulder_hip_ratio < 0.67):
                fall_indicators.append('unusual_proportions')
        
        has_horizontal_posture = 'horizontal_body' in fall_indicators
        has_tilted_low_posture = 'body_tilt' in fall_indicators and 'low_hip' in fall_indicators
        fall_detected = len(fall_indicators) >= 2 and (has_horizontal_posture or has_tilted_low_posture)
        confidence = visibility if fall_detected else 0.0
        
        details = {
            'body_angle': body_angle,
            'relative_hip_height': relative_hip_height,
            'knee_angle': avg_knee_angle,
            'shoulder_hip_ratio': shoulder_hip_ratio,
            'fall_indicators': fall_indicators,
            'visibility': visibility,
            'visible_points': visible_points,
            'required_visible_points': 6,
            'complete_body': visible_points == len(required_keypoints)
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

    def _get_average_point(self, points):
        count = len(points)
        return type('obj', (object,), {
            'x': sum(point.x for point in points) / count,
            'y': sum(point.y for point in points) / count,
            'z': sum(point.z for point in points) / count,
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
