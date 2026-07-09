from datetime import datetime, timedelta, timezone

from ..extensions import db


class AlarmEvent(db.Model):
    SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    ESCALATION_TIMEOUTS = {
        0: None,
        1: 600,
        2: 300,
    }

    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.String(64), nullable=False, index=True)
    zone_id = db.Column(db.Integer, nullable=True)
    event_type = db.Column(db.String(40), nullable=False, default="intrusion")
    title = db.Column(db.String(120), nullable=False, default="Perimeter intrusion")
    description = db.Column(db.String(500), nullable=True)
    severity = db.Column(db.String(20), nullable=False, default="medium")
    status = db.Column(db.String(20), nullable=False, default="pending")
    confidence = db.Column(db.Float, nullable=True)
    snapshot_url = db.Column(db.String(500), nullable=True)
    clip_url = db.Column(db.String(500), nullable=True)
    detection_data = db.Column(db.JSON, nullable=True)
    occurred_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    handled_at = db.Column(db.DateTime, nullable=True)
    handler_id = db.Column(db.Integer, nullable=True)
    handled_by = db.Column(db.String(64), nullable=True)
    handle_note = db.Column(db.String(500), nullable=True)
    escalation_level = db.Column(db.Integer, nullable=False, default=0)
    escalation_deadline = db.Column(db.DateTime, nullable=True)
    dingtalk_notified = db.Column(db.Boolean, nullable=False, default=False)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def mark_handled(self, username, note=""):
        self.status = "handled"
        self.handled_by = username
        self.handle_note = note
        self.handled_at = datetime.now(timezone.utc)
        self.escalation_deadline = None

    def should_escalate(self):
        if self.status in {"handled", "resolved", "false_positive"}:
            return False
        if not self.escalation_deadline:
            return False
        deadline = self.escalation_deadline
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > deadline

    def escalate(self):
        next_level = self.escalation_level + 1
        if next_level > 2:
            return False

        self.escalation_level = next_level
        timeout_seconds = self.ESCALATION_TIMEOUTS.get(next_level, 300)
        self.escalation_deadline = (
            datetime.now(timezone.utc) + timedelta(seconds=timeout_seconds)
            if timeout_seconds
            else None
        )
        return True

    def to_dict(self):
        return {
            "id": self.id,
            "cameraId": self.camera_id,
            "camera_id": self.camera_id,
            "zoneId": self.zone_id,
            "zone_id": self.zone_id,
            "eventType": self.event_type,
            "event_type": self.event_type,
            "type": self.event_type,
            "title": self.title,
            "description": self.description,
            "severity": self.severity,
            "status": self.status,
            "confidence": self.confidence,
            "snapshotUrl": self.snapshot_url,
            "snapshot_url": self.snapshot_url,
            "clipUrl": self.clip_url,
            "clip_url": self.clip_url,
            "detectionData": self.detection_data,
            "detection_data": self.detection_data,
            "occurredAt": self.occurred_at.isoformat(),
            "created_at": self.occurred_at.isoformat(),
            "handledAt": self.handled_at.isoformat() if self.handled_at else None,
            "handle_time": self.handled_at.isoformat() if self.handled_at else None,
            "handler_id": self.handler_id,
            "handledBy": self.handled_by,
            "handleNote": self.handle_note,
            "handle_note": self.handle_note,
            "escalationLevel": self.escalation_level,
            "escalation_level": self.escalation_level,
            "escalationDeadline": self.escalation_deadline.isoformat() if self.escalation_deadline else None,
            "escalation_deadline": self.escalation_deadline.isoformat() if self.escalation_deadline else None,
            "dingtalkNotified": self.dingtalk_notified,
            "dingtalk_notified": self.dingtalk_notified,
            "updatedAt": self.updated_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
