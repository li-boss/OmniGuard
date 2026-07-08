class YOLODetector:
    def __init__(self, model=None):
        self.model = model or {"name": "mock-yolo"}

    def detect_frame(self, frame):
        if isinstance(frame, dict) and frame.get("detections"):
            return frame["detections"]
        return []
