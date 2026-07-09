import base64
import hashlib
import math
from pathlib import Path
import threading
from urllib.request import urlretrieve


try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None


WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"
YUNET_MODEL = WEIGHTS_DIR / "face_detection_yunet_2023mar.onnx"
SFACE_MODEL = WEIGHTS_DIR / "face_recognition_sface_2021dec.onnx"
YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"
SFACE_COSINE_THRESHOLD = 0.363
SFACE_DISTANCE_THRESHOLD = 1.0 - SFACE_COSINE_THRESHOLD
SFACE_FEATURE_DIM = 128


class FaceRecognizer:
    _model_lock = threading.Lock()

    def __init__(self, app=None, threshold=SFACE_DISTANCE_THRESHOLD):
        self.app = app
        self.threshold = threshold
        self.detector = None
        self.recognizer = None
        self.haar_detector = None
        self.model_name = "fallback"
        if cv2 is not None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.haar_detector = cv2.CascadeClassifier(cascade_path)

    def extract_feature(self, image_data):
        image = self._decode_image(image_data)
        if image is None:
            return self._fallback_feature(image_data)

        face = self._largest_face(image)
        if face is None:
            return None

        feature = self._feature_from_face(image, face)
        return feature if feature is not None else self._fallback_feature(image_data)

    def detect_faces(self, frame):
        return [item["box"] for item in self.detect_faces_detailed(frame)]

    def detect_faces_detailed(self, frame):
        if cv2 is None or frame is None or getattr(frame, "size", 0) == 0:
            return []

        models = self._load_deep_models()
        if models:
            detector, _recognizer = models
            height, width = frame.shape[:2]
            detector.setInputSize((width, height))
            _retval, faces = detector.detect(frame)
            if faces is None:
                return []
            result = []
            for raw_face in faces:
                x, y, face_width, face_height = [int(round(value)) for value in raw_face[:4]]
                x = max(0, x)
                y = max(0, y)
                face_width = max(0, min(face_width, width - x))
                face_height = max(0, min(face_height, height - y))
                if face_width <= 0 or face_height <= 0:
                    continue
                result.append({
                    "box": [x, y, face_width, face_height],
                    "raw": raw_face,
                    "score": float(raw_face[-1]),
                })
            return sorted(result, key=lambda item: item["box"][2] * item["box"][3], reverse=True)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self.haar_detector.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(48, 48),
        )
        return [
            {"box": [int(x), int(y), int(width), int(height)], "raw": None, "score": None}
            for x, y, width, height in sorted(faces, key=lambda item: item[2] * item[3], reverse=True)
        ]

    def recognize_frame(self, frame, known_faces=None, threshold=None):
        threshold = threshold if threshold is not None else self.threshold
        known_faces = known_faces or []
        results = []

        for face in self.detect_faces_detailed(frame):
            feature = self._feature_from_face(frame, face)
            matched, distance = self.match(feature, known_faces, threshold=threshold)
            confidence = 0.0 if distance is None else max(0.0, min(1.0, 1.0 - distance))
            results.append({
                "box": face["box"],
                "name": matched["name"] if matched else "Unknown",
                "studentId": matched.get("studentId") if matched else None,
                "faceId": matched.get("id") if matched else None,
                "matched": bool(matched),
                "distance": distance,
                "confidence": confidence,
                "detectorScore": face.get("score"),
                "model": self.model_name,
            })
        return results

    def match(self, feature, known_faces, threshold=None):
        threshold = threshold if threshold is not None else self.threshold
        if not feature:
            return None, None

        best = None
        best_distance = None
        for face in known_faces:
            other = face.get("feature") or []
            if len(other) != len(feature):
                continue
            distance = self._cosine_distance(feature, other)
            if best_distance is None or distance < best_distance:
                best = face
                best_distance = distance

        if best is not None and best_distance is not None and best_distance <= threshold:
            return best, best_distance
        return None, best_distance

    def compare(self, known_feature, candidate_feature, threshold=None):
        threshold = threshold if threshold is not None else self.threshold
        if not known_feature or not candidate_feature or len(known_feature) != len(candidate_feature):
            return {"matched": False, "distance": 1.0}
        distance = self._cosine_distance(known_feature, candidate_feature)
        return {"matched": distance <= threshold, "distance": distance}

    def detect_and_recognize_in_person(self, frame, person_box):
        return False, None, "Stranger", None, 1.0

    def _load_deep_models(self):
        if cv2 is None:
            return None
        if self.detector is not None and self.recognizer is not None:
            return self.detector, self.recognizer

        with self._model_lock:
            try:
                self._ensure_model_file(YUNET_MODEL, YUNET_URL, min_bytes=100_000)
                self._ensure_model_file(SFACE_MODEL, SFACE_URL, min_bytes=10_000_000)
                self.detector = cv2.FaceDetectorYN_create(
                    str(YUNET_MODEL),
                    "",
                    (320, 320),
                    0.62,
                    0.3,
                    5000,
                )
                self.recognizer = cv2.FaceRecognizerSF_create(str(SFACE_MODEL), "")
                self.model_name = "YuNet/SFace"
                return self.detector, self.recognizer
            except Exception:
                self.detector = None
                self.recognizer = None
                self.model_name = "Haar/fallback"
                return None

    def _feature_from_face(self, frame, face):
        models = self._load_deep_models()
        if models and face.get("raw") is not None:
            _detector, recognizer = models
            aligned = recognizer.alignCrop(frame, face["raw"])
            feature = recognizer.feature(aligned).flatten().astype("float32")
            norm = float(np.linalg.norm(feature))
            if norm > 0:
                feature = feature / norm
            return [round(float(value), 8) for value in feature]

        x, y, width, height = face["box"]
        crop = frame[y:y + height, x:x + width]
        return self._fallback_feature(crop)

    def _largest_face(self, image):
        faces = self.detect_faces_detailed(image)
        return faces[0] if faces else None

    def _decode_image(self, image_data):
        if cv2 is None or np is None or image_data is None:
            return None
        if hasattr(image_data, "size"):
            return image_data if image_data.size else None
        if not isinstance(image_data, str):
            return None

        raw = image_data.split(",", 1)[-1]
        try:
            payload = base64.b64decode(raw + "===")
        except Exception:
            return None
        data = np.frombuffer(payload, dtype=np.uint8)
        image = cv2.imdecode(data, cv2.IMREAD_COLOR)
        return image

    def _fallback_feature(self, image_data):
        if image_data is None:
            return None
        if hasattr(image_data, "size") and image_data.size == 0:
            return None
        if isinstance(image_data, str):
            payload = image_data.encode("utf-8", errors="ignore")
        elif hasattr(image_data, "tobytes"):
            payload = image_data.tobytes()
        else:
            payload = str(image_data).encode("utf-8", errors="ignore")
        digest = hashlib.sha512(payload).digest()
        values = list(digest) * 2
        vector = [(value / 255.0) for value in values[:SFACE_FEATURE_DIM]]
        mean = sum(vector) / len(vector)
        variance = sum((value - mean) ** 2 for value in vector) / len(vector)
        scale = math.sqrt(variance) + 1e-6
        return [round((value - mean) / scale, 6) for value in vector]

    def _cosine_distance(self, left, right):
        dot = 0.0
        left_norm = 0.0
        right_norm = 0.0
        for a, b in zip(left, right):
            a = float(a)
            b = float(b)
            dot += a * b
            left_norm += a * a
            right_norm += b * b
        if left_norm <= 0 or right_norm <= 0:
            return 1.0
        similarity = dot / (math.sqrt(left_norm) * math.sqrt(right_norm))
        return float(1.0 - similarity)

    def _ensure_model_file(self, path, url, min_bytes):
        if path.exists() and path.stat().st_size >= min_bytes:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(url, path)
        if not path.exists() or path.stat().st_size < min_bytes:
            raise RuntimeError(f"model download failed: {path.name}")
