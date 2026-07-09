from datetime import datetime, timezone
import json

from ..extensions import db


FACE_FEATURE_DIM = 128
MAX_FACE_SAMPLES = 10


class FaceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    feature_json = db.Column(db.Text, nullable=False, default="[]")
    image_preview = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def set_feature(self, feature):
        self.set_features([feature] if feature else [])

    def set_features(self, features):
        self.feature_json = json.dumps(self._clean_features(features)[:MAX_FACE_SAMPLES])

    def add_features(self, features):
        existing = self.get_features()
        added = 0
        for feature in self._clean_features(features):
            if self._is_duplicate_feature(feature, existing):
                continue
            existing.append(feature)
            added += 1
        self.feature_json = json.dumps(existing[-MAX_FACE_SAMPLES:])
        return added

    def get_feature(self):
        features = self.get_features()
        return features[0] if features else []

    def get_features(self):
        value = json.loads(self.feature_json or "[]")
        return self._clean_features(value)

    def feature_count(self):
        return len(self.get_features())

    def to_dict(self):
        return {
            "id": self.id,
            "studentId": self.student_id,
            "name": self.name,
            "imagePreview": self.image_preview,
            "sampleCount": self.feature_count(),
            "featureCount": self.feature_count(),
            "createdAt": self.created_at.isoformat(),
        }

    def _clean_features(self, value):
        if self._is_feature_vector(value):
            return [self._normalize_feature(value)]
        if not isinstance(value, list):
            return []

        features = []
        for item in value:
            if self._is_feature_vector(item):
                features.append(self._normalize_feature(item))
        return features

    def _is_feature_vector(self, value):
        return (
            isinstance(value, list)
            and len(value) == FACE_FEATURE_DIM
            and all(isinstance(item, (int, float)) for item in value)
        )

    def _normalize_feature(self, feature):
        return [round(float(value), 8) for value in feature]

    def _is_duplicate_feature(self, feature, existing):
        return any(self._cosine_distance(feature, other) < 0.02 for other in existing)

    def _cosine_distance(self, left, right):
        dot = 0.0
        left_norm = 0.0
        right_norm = 0.0
        for a, b in zip(left, right):
            dot += a * b
            left_norm += a * a
            right_norm += b * b
        if left_norm <= 0 or right_norm <= 0:
            return 1.0
        return 1.0 - dot / ((left_norm ** 0.5) * (right_norm ** 0.5))
