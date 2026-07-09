import base64
import hashlib
import math


class FaceRecognizer:
    def __init__(self, app=None, threshold=0.6):
        self.app = app
        self.threshold = threshold

    def extract_feature(self, image_data):
        if image_data is None:
            return None
        if hasattr(image_data, "size") and image_data.size == 0:
            return None
        if isinstance(image_data, str):
            raw = image_data.split(",", 1)[-1]
            try:
                payload = base64.b64decode(raw + "===")
            except Exception:
                payload = raw.encode("utf-8", errors="ignore")
        elif hasattr(image_data, "tobytes"):
            payload = image_data.tobytes()
        else:
            payload = str(image_data).encode("utf-8", errors="ignore")

        digest = hashlib.sha256(payload).digest()
        return [round(value / 255, 6) for value in digest[:32]]

    def match(self, feature, known_faces, threshold=0.18):
        best = None
        best_distance = None
        for face in known_faces:
            other = face.get("feature") or []
            if len(other) != len(feature):
                continue
            distance = sum(abs(a - b) for a, b in zip(feature, other)) / len(feature)
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
        distance = math.sqrt(sum((float(a) - float(b)) ** 2 for a, b in zip(known_feature, candidate_feature)))
        return {"matched": distance <= threshold, "distance": distance}

    def detect_and_recognize_in_person(self, frame, person_box):
        return False, None, "Stranger", None, 1.0
