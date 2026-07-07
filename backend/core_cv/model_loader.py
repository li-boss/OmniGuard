from functools import lru_cache

from ultralytics import YOLO


@lru_cache(maxsize=4)
def load_yolo_model(weight_path):
    return YOLO(weight_path)
