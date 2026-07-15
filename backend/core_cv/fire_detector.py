import logging
import cv2
import numpy as np
from pathlib import Path

logger = logging.getLogger(__name__)


class FireDetector:
    def __init__(self, model_path=None, confidence_threshold=0.5):
        self.confidence_threshold = confidence_threshold
        self.model = None
        self.class_names = ['fire', 'smoke']
        
        # Temporal consensus for color-based detection: require N consecutive fire-positive frames
        self._consecutive_fire_count = 0
        self._min_consecutive_frames = 3
        
        if model_path is None:
            model_path = Path(__file__).parent / 'weights' / 'fire_yolov8n.pt'
        
        self.model_path = Path(model_path)
        
        try:
            from ultralytics import YOLO
            self.yolo_available = True
        except ImportError:
            self.yolo_available = False
            logger.warning("Ultralytics not installed. Fire detection will be disabled.")
            return
        
        self._load_model()
    
    def _load_model(self):
        if not self.yolo_available:
            return
        
        try:
            if self.model_path.exists():
                self.model = YOLO(str(self.model_path))
                logger.info(f"Fire detection model loaded from {self.model_path}")
            else:
                logger.warning(f"Fire detection model not found at {self.model_path}")
                logger.info("Fire detection will use color-based detection as fallback")
                self.model = None
        except Exception as e:
            logger.error(f"Error loading fire detection model: {e}")
            self.model = None
    
    def detect(self, frame):
        if frame is None:
            return None
        
        results = {
            'fire_detected': False,
            'smoke_detected': False,
            'detections': [],
            'confidence': 0.0
        }
        
        if self.model is not None:
            yolo_results = self._detect_with_yolo(frame)
            if yolo_results:
                results.update(yolo_results)
        else:
            color_results = self._detect_with_color(frame)
            if color_results:
                results.update(color_results)
        
        return results
    
    def _detect_with_yolo(self, frame):
        try:
            predictions = self.model(frame, verbose=False)
            
            detections = []
            fire_detected = False
            smoke_detected = False
            max_confidence = 0.0
            
            for pred in predictions:
                boxes = pred.boxes
                for box in boxes:
                    conf = float(box.conf[0])
                    cls = int(box.cls[0])
                    
                    if conf < self.confidence_threshold:
                        continue
                    
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    
                    detection = {
                        'bbox': [int(x1), int(y1), int(x2-x1), int(y2-y1)],
                        'confidence': conf,
                        'class': self.class_names[cls] if cls < len(self.class_names) else 'unknown'
                    }
                    detections.append(detection)
                    
                    if detection['class'] == 'fire':
                        fire_detected = True
                        max_confidence = max(max_confidence, conf)
                    elif detection['class'] == 'smoke':
                        smoke_detected = True
                        max_confidence = max(max_confidence, conf)
            
            return {
                'fire_detected': fire_detected,
                'smoke_detected': smoke_detected,
                'detections': detections,
                'confidence': max_confidence
            }
            
        except Exception as e:
            logger.error(f"Error in YOLO fire detection: {e}")
            return None
    
    def _detect_with_color(self, frame):
        try:
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Moderate HSV ranges — balanced between catching real fire and filtering warm objects:
            # - S_min=60 (above typical skin/wood saturation of 30-50, below flame's ~100+)
            # - V_min=180 (above room lighting, below bright flame center)
            # - H range for orange: 15-40 (excludes deep brown at 40-50)
            lower_fire1 = np.array([0, 60, 180])
            upper_fire1 = np.array([15, 255, 255])
            lower_fire2 = np.array([165, 60, 180])
            upper_fire2 = np.array([180, 255, 255])
            lower_fire3 = np.array([15, 60, 200])
            upper_fire3 = np.array([40, 255, 255])
            
            mask1 = cv2.inRange(hsv, lower_fire1, upper_fire1)
            mask2 = cv2.inRange(hsv, lower_fire2, upper_fire2)
            mask3 = cv2.inRange(hsv, lower_fire3, upper_fire3)
            fire_mask = cv2.bitwise_or(mask1, cv2.bitwise_or(mask2, mask3))
            
            fire_pixels = cv2.countNonZero(fire_mask)
            total_pixels = frame.shape[0] * frame.shape[1]
            fire_ratio = fire_pixels / total_pixels
            
            # Moderate threshold — 7% filters scattered warm pixels (FP at 6.3%) but catches real fire
            fire_detected = fire_ratio > 0.07
            
            smoke_detected = False
            smoke_ratio = 0.0
            
            if fire_ratio > 0.001:
                logger.info(f"Fire detection: ratio={fire_ratio:.6f}, threshold=0.07, fire_pixels={fire_pixels}, detected={fire_detected}")
            
            # Temporal consensus: require N consecutive fire-positive frames
            if fire_detected:
                self._consecutive_fire_count += 1
                if self._consecutive_fire_count < self._min_consecutive_frames:
                    fire_detected = False  # Suppress until consensus is reached
                    logger.debug(f"Fire color match but waiting for consensus: {self._consecutive_fire_count}/{self._min_consecutive_frames}")
            else:
                self._consecutive_fire_count = 0  # Reset counter on negative frame
            
            detections = []
            if fire_detected:
                contours, _ = cv2.findContours(fire_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    # Increase min contour area from 100→500 to filter scattered noise pixels
                    if cv2.contourArea(contour) > 500:
                        x, y, w, h = cv2.boundingRect(contour)
                        detections.append({
                            'bbox': [x, y, w, h],
                            'confidence': fire_ratio,
                            'class': 'fire'
                        })
            
            return {
                'fire_detected': fire_detected,
                'smoke_detected': smoke_detected,
                'detections': detections,
                'confidence': max(fire_ratio, smoke_ratio)
            }
            
        except Exception as e:
            logger.error(f"Error in color-based fire detection: {e}")
            return None
    
    def close(self):
        logger.info("FireDetector closed")