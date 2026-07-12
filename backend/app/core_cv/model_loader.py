import os
import threading
from pathlib import Path

import cv2


class ModelLoader:
    _models = {}
    _lock = threading.RLock()
    WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"

    @classmethod
    def get_yolo(cls):
        """Load the fire detector once and share it between camera pipelines."""
        with cls._lock:
            if "yolo" not in cls._models:
                configured_path = os.getenv("FIRE_MODEL_PATH")
                model_path = Path(configured_path) if configured_path else cls.WEIGHTS_DIR / "fire_smoke_yolov8n.onnx"
                if configured_path and not model_path.is_absolute():
                    model_path = Path(__file__).resolve().parents[2] / model_path
                if not model_path.is_file():
                    raise FileNotFoundError(
                        f"Fire model not found: {model_path}. "
                        "Run backend/scripts/download_fire_model.ps1 first."
                    )
                cls._models["yolo"] = {
                    "name": "yolov8n-fire-smoke",
                    "path": str(model_path),
                    "net": cv2.dnn.readNetFromONNX(str(model_path)),
                    "lock": threading.Lock(),
                    "classes": ("fire", "smoke"),
                    "output_format": "yolov8",
                    "input_size": 640,
                    "ready": True,
                }
            return cls._models["yolo"]

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
