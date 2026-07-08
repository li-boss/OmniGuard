from datetime import datetime, timezone
import json

from ..extensions import db


class Zone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    rule_type = db.Column(db.String(32), nullable=False, default="intrusion")
    points_json = db.Column(db.Text, nullable=False, default="[]")
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def set_points(self, points):
        self.points_json = json.dumps(points)

    def get_points(self):
        return json.loads(self.points_json or "[]")

    def to_dict(self):
        return {
            "id": self.id,
            "cameraId": self.camera_id,
            "name": self.name,
            "ruleType": self.rule_type,
            "points": self.get_points(),
            "enabled": self.enabled,
            "createdAt": self.created_at.isoformat(),
        }
