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
    logger.warning(f"MediaPipe not installed or import failed: {e}. Hand raise detection will be disabled.")

HAND_RAISE_DETECTOR_AVAILABLE = MEDIAPIPE_AVAILABLE


class HandRaiseDetector:
    """
    Detect hand raising behavior using MediaPipe pose estimation.
    Triggers when:
    1. Wrist is above shoulder
    2. Arm is extended (elbow angle > 120°)
    3. Confidence threshold is met
    """
    def __init__(self, 
                 height_threshold=0.05,
                 elbow_angle_threshold=100,
                 confidence_threshold=0.3):
        if not MEDIAPIPE_AVAILABLE:
            raise ImportError("MediaPipe is required for hand raise detection")
        
        self.height_threshold = height_threshold
        self.elbow_angle_threshold = elbow_angle_threshold
        self.confidence_threshold = confidence_threshold
        
        model_path = self._get_pose_model()
        
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.IMAGE,
            num_poses=1,
            min_pose_detection_confidence=0.3,
            min_pose_presence_confidence=0.3,
            min_tracking_confidence=0.3
        )
        self.pose = vision.PoseLandmarker.create_from_options(options)
        self.timestamp = 0
        
        logger.info("HandRaiseDetector initialized with MediaPipe Task API")
    
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
        """
        Detect hand raising in the given frame.
        
        Args:
            frame: BGR image
            bbox: Optional bounding box [x1, y1, x2, y2] to crop
            
        Returns:
            dict with keys:
                - hand_raised: bool (True if hand is raised)
                - confidence: float (0-1)
                - details: dict (detection details)
                - landmarks: MediaPipe landmarks
        """
        if frame is None:
            return None
        
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Crop to bbox if provided
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
            
            hand_raised, confidence, details = self._analyze_pose(landmarks)
            
            return {
                'hand_raised': hand_raised,
                'confidence': confidence,
                'details': details,
                'landmarks': landmarks
            }
            
        except Exception as e:
            logger.error(f"Error in hand raise detection: {e}")
            return None
    
    def _analyze_pose(self, landmarks):
        """
        Analyze pose landmarks to detect hand raising.
        
        Checks:
        1. Wrist above shoulder (y-coordinate, lower y = higher position)
        2. Elbow angle (arm extension)
        3. Arm visibility
        """
        # MediaPipe pose landmark indices
        LEFT_SHOULDER = 11
        RIGHT_SHOULDER = 12
        LEFT_ELBOW = 13
        RIGHT_ELBOW = 14
        LEFT_WRIST = 15
        RIGHT_WRIST = 16
        
        MIN_VISIBILITY = 0.3
        
        # Extract landmarks
        left_shoulder = landmarks[LEFT_SHOULDER]
        right_shoulder = landmarks[RIGHT_SHOULDER]
        left_elbow = landmarks[LEFT_ELBOW]
        right_elbow = landmarks[RIGHT_ELBOW]
        left_wrist = landmarks[LEFT_WRIST]
        right_wrist = landmarks[RIGHT_WRIST]
        
        # Check visibility
        left_arm_visible = (
            left_shoulder.visibility >= MIN_VISIBILITY and
            left_elbow.visibility >= MIN_VISIBILITY and
            left_wrist.visibility >= MIN_VISIBILITY
        )
        
        right_arm_visible = (
            right_shoulder.visibility >= MIN_VISIBILITY and
            right_elbow.visibility >= MIN_VISIBILITY and
            right_wrist.visibility >= MIN_VISIBILITY
        )
        
        if not left_arm_visible and not right_arm_visible:
            logger.debug("No visible arms for hand raise detection")
            return False, 0.0, {
                'reason': 'no_visible_arms',
                'left_arm_visible': False,
                'right_arm_visible': False,
                'hand_raised_indicators': [],
            }
        
        hand_raised_indicators = []
        
        # Check left arm
        left_hand_raised = False
        if left_arm_visible:
            # 1. Wrist above shoulder (lower y = higher position)
            wrist_above_shoulder = left_wrist.y < (left_shoulder.y - self.height_threshold)
            
            # 2. Elbow angle (arm extension)
            left_elbow_angle = self._calculate_angle(left_shoulder, left_elbow, left_wrist)
            arm_extended = left_elbow_angle > self.elbow_angle_threshold
            
            # 3. Wrist is higher than elbow (arm going upward)
            wrist_above_elbow = left_wrist.y < left_elbow.y
            
            if wrist_above_shoulder and arm_extended:
                hand_raised_indicators.append('left_hand_raised')
                left_hand_raised = True
            
            logger.debug(
                f"Left arm: wrist_y={left_wrist.y:.2f}, shoulder_y={left_shoulder.y:.2f}, "
                f"elbow_angle={left_elbow_angle:.1f}°, raised={left_hand_raised}"
            )
        
        # Check right arm
        right_hand_raised = False
        if right_arm_visible:
            # 1. Wrist above shoulder
            wrist_above_shoulder = right_wrist.y < (right_shoulder.y - self.height_threshold)
            
            # 2. Elbow angle
            right_elbow_angle = self._calculate_angle(right_shoulder, right_elbow, right_wrist)
            arm_extended = right_elbow_angle > self.elbow_angle_threshold
            
            # 3. Wrist is higher than elbow
            wrist_above_elbow = right_wrist.y < right_elbow.y
            
            if wrist_above_shoulder and arm_extended:
                hand_raised_indicators.append('right_hand_raised')
                right_hand_raised = True
            
            logger.debug(
                f"Right arm: wrist_y={right_wrist.y:.2f}, shoulder_y={right_shoulder.y:.2f}, "
                f"elbow_angle={right_elbow_angle:.1f}°, raised={right_hand_raised}"
            )
        
        # Determine if hand is raised
        hand_raised = left_hand_raised or right_hand_raised
        
        # Calculate confidence based on visibility and indicators
        if hand_raised:
            visibility_scores = []
            if left_hand_raised:
                visibility_scores.extend([
                    left_shoulder.visibility,
                    left_elbow.visibility,
                    left_wrist.visibility
                ])
            if right_hand_raised:
                visibility_scores.extend([
                    right_shoulder.visibility,
                    right_elbow.visibility,
                    right_wrist.visibility
                ])
            confidence = min(visibility_scores) if visibility_scores else 0.0
        else:
            confidence = 0.0
        
        details = {
            'left_arm_visible': left_arm_visible,
            'right_arm_visible': right_arm_visible,
            'left_hand_raised': left_hand_raised,
            'right_hand_raised': right_hand_raised,
            'hand_raised_indicators': hand_raised_indicators,
            'left_elbow_angle': left_elbow_angle if left_arm_visible else None,
            'right_elbow_angle': right_elbow_angle if right_arm_visible else None,
        }
        
        return hand_raised, confidence, details
    
    def _calculate_angle(self, point1, point2, point3):
        """
        Calculate angle at point2 formed by point1-point2-point3.
        
        Args:
            point1, point2, point3: MediaPipe landmarks with x, y attributes
            
        Returns:
            angle in degrees
        """
        v1 = np.array([point1.x - point2.x, point1.y - point2.y])
        v2 = np.array([point3.x - point2.x, point3.y - point2.y])
        
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-6)
        cos_angle = np.clip(cos_angle, -1.0, 1.0)
        angle = np.degrees(np.arccos(cos_angle))
        
        return angle
    
    def close(self):
        if hasattr(self, 'pose'):
            self.pose.close()
        logger.info("HandRaiseDetector closed")