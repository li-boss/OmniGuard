import base64
import hashlib


class FaceRecognizer:
    def extract_feature(self, image_data):
        raw = image_data.split(",", 1)[-1] if isinstance(image_data, str) else ""
        try:
            payload = base64.b64decode(raw + "===")
        except Exception:
            payload = raw.encode("utf-8", errors="ignore")

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
