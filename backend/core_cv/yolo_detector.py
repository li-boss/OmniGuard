import logging
from .model_loader import ModelLoader

logger = logging.getLogger(__name__)

class YoloDetector:
    def __init__(self, weight_path=None, confidence=0.35):
        # We use ModelLoader to load the cached YOLOv8 model
        self.model = ModelLoader.get_yolo()
        self.confidence = confidence

    def detect(self, frame):
        if frame is None:
            return []
            
        h, w = frame.shape[:2]
        if h == 0 or w == 0:
            return []

        try:
            # Predict using YOLOv8
            results = self.model.predict(frame, conf=self.confidence, imgsz=320, verbose=False)
            if not results:
                return []
                
            boxes = results[0].boxes
            detections = []
            
            for box in boxes:
                # box.data returns tensor: [x1, y1, x2, y2, confidence, class_id]
                data = box.data[0].tolist()
                if len(data) < 6:
                    continue
                
                x1_abs, y1_abs, x2_abs, y2_abs, conf, class_id = data
                class_id = int(class_id)
                
                # Class 0 is 'person' in COCO dataset
                if class_id != 0:
                    continue
                
                # Normalize coordinates and bound to [0.0, 1.0]
                x1_norm = max(0.0, min(1.0, x1_abs / w))
                y1_norm = max(0.0, min(1.0, y1_abs / h))
                x2_norm = max(0.0, min(1.0, x2_abs / w))
                y2_norm = max(0.0, min(1.0, y2_abs / h))
                
                detections.append({
                    "box": [int(x1_abs), int(y1_abs), int(x2_abs), int(y2_abs)],
                    "box_norm": [x1_norm, y1_norm, x2_norm, y2_norm],
                    "conf": float(conf),
                    "class_id": class_id
                })
                
            return detections
            
        except Exception as e:
            logger.error(f"Error during YOLO detection: {e}")
            return []
