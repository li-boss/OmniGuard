from datetime import datetime, timezone

from ..extensions import db


class AlarmEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.String(64), nullable=False, index=True)
    zone_id = db.Column(db.Integer, nullable=True)
    event_type = db.Column(db.String(40), nullable=False, default="intrusion")
    title = db.Column(db.String(120), nullable=False, default="围栏入侵")
    description = db.Column(db.String(500), nullable=True)
    severity = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="pending")
    confidence = db.Column(db.Float, nullable=True)
    snapshot_url = db.Column(db.String(500), nullable=True)
    clip_url = db.Column(db.String(500), nullable=True)
    occurred_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    handled_at = db.Column(db.DateTime, nullable=True)
    handled_by = db.Column(db.String(64), nullable=True)
    handle_note = db.Column(db.String(500), nullable=True)

    def mark_handled(self, username, note=""):
        self.status = "handled"
        self.handled_by = username
        self.handle_note = note
        self.handled_at = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            "id": self.id,
            "cameraId": self.camera_id,
            "zoneId": self.zone_id,
            "eventType": self.event_type,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "confidence": self.confidence,
            "snapshotUrl": self.snapshot_url,
            "clipUrl": self.clip_url,
            "occurredAt": self.occurred_at.isoformat(),
            "handledAt": self.handled_at.isoformat() if self.handled_at else None,
            "handledBy": self.handled_by,
            "handleNote": self.handle_note,
        }
