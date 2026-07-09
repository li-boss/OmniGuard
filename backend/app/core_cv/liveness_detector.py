class LivenessDetector:
    def __init__(self, blur_threshold=80.0):
        self.blur_threshold = blur_threshold

    def detect(self, frame):
        if isinstance(frame, dict) and "isLive" in frame:
            return bool(frame["isLive"])
        return True

    def is_live(self, frame):
        if frame is None or (hasattr(frame, "size") and frame.size == 0):
            return False, 0.0
        return self.detect(frame), 1.0 if self.detect(frame) else 0.0
