class YOLODetector:
    def __init__(self, model=None):
        self.model = model or {"name": "mock-yolo"}

    def detect_frame(self, frame):
        if isinstance(frame, dict) and frame.get("detections"):
            return frame["detections"]
        return []

    def detect(self, frame):
        return self.detect_frame(frame)


YoloDetector = YOLODetector
