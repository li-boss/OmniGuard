from .model_loader import load_yolo_model


class YoloDetector:
    def __init__(self, weight_path, confidence=0.35):
        self.model = load_yolo_model(weight_path)
        self.confidence = confidence

    def detect(self, frame):
        results = self.model.predict(frame, conf=self.confidence, verbose=False)
        return results[0].boxes.data.tolist() if results else []
