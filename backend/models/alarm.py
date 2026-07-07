from datetime import datetime

from extensions import db


class AlarmEvent(db.Model):
    """告警事件模型"""

    __tablename__ = "alarm_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    camera_id = db.Column(
        db.String(64),
        nullable=False
    )

    alarm_type = db.Column(
        db.String(32),
        nullable=False
    )

    severity = db.Column(
        db.String(16),
        default="low"
    )

    content = db.Column(
        db.Text
    )

    handle_status = db.Column(
        db.String(16),
        default="pending"
    )

    handle_note = db.Column(
        db.Text
    )

    create_time = db.Column(
        db.DateTime,
        default=datetime.now
    )

    update_time = db.Column(
        db.DateTime,
        default=datetime.now,
        onupdate=datetime.now
    )

    def to_dict(self):
        return {
            "id": self.id,
            "camera_id": self.camera_id,
            "alarm_type": self.alarm_type,
            "severity": self.severity,
            "content": self.content,
            "handle_status": self.handle_status,
            "handle_note": self.handle_note,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S")
            if self.create_time else ""
        }