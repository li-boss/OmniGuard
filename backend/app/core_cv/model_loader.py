class ModelLoader:
    def __init__(self):
        self._models = {}

    def get_yolo(self):
        return self._models.setdefault("yolo", {"name": "mock-yolo", "ready": True})

    def get_face_detector(self):
        return self._models.setdefault("face_detector", {"name": "mock-face-detector"})

    def get_face_recognizer(self):
        return self._models.setdefault("face_recognizer", {"name": "hash-face-recognizer"})

    def warmup(self):
        self.get_yolo()
        self.get_face_detector()
        self.get_face_recognizer()
        return {"loaded": list(self._models.keys())}
