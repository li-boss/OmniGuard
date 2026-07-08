from datetime import datetime, timezone
import json

from ..extensions import db


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
        self.feature_json = json.dumps(feature)

    def get_feature(self):
        return json.loads(self.feature_json or "[]")

    def to_dict(self):
        return {
            "id": self.id,
            "studentId": self.student_id,
            "name": self.name,
            "imagePreview": self.image_preview,
            "createdAt": self.created_at.isoformat(),
        }
