import os

import cv2
import numpy as np

from .model_loader import ModelLoader


class YOLODetector:
    def __init__(self, model=None, confidence=None, iou_threshold=None):
        self.model = model or ModelLoader.get_yolo()
        self.confidence = float(confidence or os.getenv("FIRE_CONFIDENCE", "0.25"))
        self.iou_threshold = float(iou_threshold or os.getenv("FIRE_NMS_IOU", "0.45"))

    @staticmethod
    def _letterbox(frame, size):
        height, width = frame.shape[:2]
        scale = min(size / width, size / height)
        resized_width, resized_height = round(width * scale), round(height * scale)
        resized = cv2.resize(frame, (resized_width, resized_height))
        canvas = np.full((size, size, 3), 114, dtype=np.uint8)
        left = (size - resized_width) // 2
        top = (size - resized_height) // 2
        canvas[top:top + resized_height, left:left + resized_width] = resized
        return canvas, scale, left, top

    def detect_frame(self, frame):
        # Preserve the synthetic detection hook used by API/unit tests.
        if isinstance(frame, dict):
            return frame.get("detections", [])
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return []

        size = self.model["input_size"]
        image, scale, pad_x, pad_y = self._letterbox(frame, size)
        blob = cv2.dnn.blobFromImage(image, 1 / 255.0, (size, size), swapRB=True)
        with self.model["lock"]:
            self.model["net"].setInput(blob)
            output = self.model["net"].forward()

        predictions = np.squeeze(output)
        if predictions.ndim == 2 and predictions.shape[0] < predictions.shape[1]:
            predictions = predictions.T
        if predictions.ndim != 2 or predictions.shape[1] < 6:
            return []

        boxes, scores, class_ids = [], [], []
        for row in predictions:
            if self.model.get("output_format") == "yolov8":
                class_scores = row[4:]
                class_id = int(np.argmax(class_scores))
                score = float(class_scores[class_id])
            else:
                objectness = float(row[4])
                class_id = int(np.argmax(row[5:]))
                score = objectness * float(row[5 + class_id])
            class_name = self.model["classes"][class_id]
            class_threshold = self.confidence
            if class_name == "smoke":
                class_threshold = float(os.getenv("SMOKE_CONFIDENCE", "0.60"))
            if score < class_threshold:
                continue
            center_x, center_y, width, height = row[:4]
            x = (float(center_x) - float(width) / 2 - pad_x) / scale
            y = (float(center_y) - float(height) / 2 - pad_y) / scale
            boxes.append([round(x), round(y), round(float(width) / scale), round(float(height) / scale)])
            scores.append(score)
            class_ids.append(class_id)

        kept = cv2.dnn.NMSBoxes(boxes, scores, self.confidence, self.iou_threshold)
        frame_height, frame_width = frame.shape[:2]
        detections = []
        for index in np.asarray(kept).reshape(-1):
            x, y, width, height = boxes[int(index)]
            x1, y1 = max(0, x), max(0, y)
            x2, y2 = min(frame_width, x + width), min(frame_height, y + height)
            if x2 <= x1 or y2 <= y1:
                continue
            class_id = class_ids[int(index)]
            confidence = round(float(scores[int(index)]), 4)
            detections.append({
                "box": [x1, y1, x2, y2],
                "bbox": [x1, y1, x2, y2],
                "box_norm": [x1 / frame_width, y1 / frame_height, x2 / frame_width, y2 / frame_height],
                "classId": class_id,
                "className": self.model["classes"][class_id],
                "eventType": self.model["classes"][class_id],
                "confidence": confidence,
                "severity": "critical" if confidence >= 0.75 else "high",
            })
        return detections

    def detect(self, frame):
        return self.detect_frame(frame)


YoloDetector = YOLODetector
