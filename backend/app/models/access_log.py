from datetime import datetime, timezone

from ..extensions import db


class AccessLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    username = db.Column(db.String(64), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    ip = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.user_id,
            "username": self.username,
            "action": self.action,
            "ip": self.ip,
            "userAgent": self.user_agent,
            "createdAt": self.created_at.isoformat(),
        }
