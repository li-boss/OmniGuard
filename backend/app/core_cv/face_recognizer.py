import base64
import hashlib
import math


try:
    import cv2
    import numpy as np
except ImportError:  # pragma: no cover - optional runtime dependency
    cv2 = None
    np = None


class FaceRecognizer:
    def __init__(self, app=None, threshold=0.55):
        self.app = app
        self.threshold = threshold
        self.detector = None
        if cv2 is not None:
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            self.detector = cv2.CascadeClassifier(cascade_path)

    def extract_feature(self, image_data):
        image = self._decode_image(image_data)
        if image is None:
            return self._fallback_feature(image_data)

        face = self._largest_face_crop(image)
        if face is None:
            face = self._center_crop(image)
        if face is None or face.size == 0:
            return None

        gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        gray = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA)
        vector = gray.astype("float32").reshape(-1)
        vector = (vector - float(vector.mean())) / (float(vector.std()) + 1e-6)
        return [round(float(value), 6) for value in vector]

    def detect_faces(self, frame):
        if cv2 is None or frame is None or getattr(frame, "size", 0) == 0:
            return []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=5,
            minSize=(48, 48),
        )
        return sorted([tuple(map(int, face)) for face in faces], key=lambda item: item[2] * item[3], reverse=True)

    def recognize_frame(self, frame, known_faces=None, threshold=None):
        threshold = threshold if threshold is not None else self.threshold
        known_faces = known_faces or []
        results = []

        for x, y, width, height in self.detect_faces(frame):
            face_crop = frame[y:y + height, x:x + width]
            feature = self.extract_feature(face_crop)
            matched, distance = self.match(feature, known_faces, threshold=threshold)
            confidence = 0.0 if distance is None else max(0.0, min(1.0, 1.0 - distance))
            results.append({
                "box": [x, y, width, height],
                "name": matched["name"] if matched else "Unknown",
                "studentId": matched.get("studentId") if matched else None,
                "faceId": matched.get("id") if matched else None,
                "matched": bool(matched),
                "distance": distance,
                "confidence": confidence,
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
        vector = [(value / 255.0) for value in values[:128]]
        mean = sum(vector) / len(vector)
        variance = sum((value - mean) ** 2 for value in vector) / len(vector)
        scale = math.sqrt(variance) + 1e-6
        return [round((value - mean) / scale, 6) for value in vector]

    def _largest_face_crop(self, image):
        faces = self.detect_faces(image)
        if not faces:
            return None
        x, y, width, height = faces[0]
        pad_x = int(width * 0.18)
        pad_y = int(height * 0.18)
        x1 = max(0, x - pad_x)
        y1 = max(0, y - pad_y)
        x2 = min(image.shape[1], x + width + pad_x)
        y2 = min(image.shape[0], y + height + pad_y)
        return image[y1:y2, x1:x2]

    def _center_crop(self, image):
        height, width = image.shape[:2]
        side = min(height, width)
        if side <= 0:
            return None
        x = (width - side) // 2
        y = (height - side) // 2
        return image[y:y + side, x:x + side]

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
