class LivenessDetector:
    def detect(self, frame):
        if isinstance(frame, dict) and "isLive" in frame:
            return bool(frame["isLive"])
        return True
