class ModelLoader:
    _models = {}

    @classmethod
    def get_yolo(cls):
        return cls._models.setdefault("yolo", {"name": "mock-yolo", "ready": True})

    @classmethod
    def get_face_detector(cls):
        return cls._models.setdefault("face_detector", {"name": "mock-face-detector"})

    @classmethod
    def get_face_recognizer(cls):
        return cls._models.setdefault("face_recognizer", {"name": "hash-face-recognizer"})

    @classmethod
    def warmup(cls):
        cls.get_yolo()
        cls.get_face_detector()
        cls.get_face_recognizer()
        return {"loaded": list(cls._models.keys())}
