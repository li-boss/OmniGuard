"""
告警模型。

Alarm 主要由 E 模块维护，但 C 模块需要先提供统一 ORM 定义，
方便数据库初始化和跨模块外键关系保持一致。
"""

from datetime import datetime, timezone

from . import db


def utc_now():
    """返回时区感知的 UTC 时间。"""

    return datetime.now(timezone.utc)


class Alarm(db.Model):
    """告警记录表。"""

    __tablename__ = "alarm"

    id = db.Column(db.Integer, primary_key=True)
    zone_id = db.Column(db.Integer, db.ForeignKey("zone.id"), nullable=True)

    alarm_type = db.Column(db.String(64), nullable=False)
    level = db.Column(db.String(32), nullable=False, default="medium")
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="open")
    device_code = db.Column(db.String(64), nullable=True)
    handled_by = db.Column(db.Integer, nullable=True)
    handle_note = db.Column(db.String(255), nullable=True)

    occurred_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    zone = db.relationship("Zone", back_populates="alarms")

    def to_dict(self):
        """转换为接口响应字典。"""

        return {
            "id": self.id,
            "zone_id": self.zone_id,
            "zone_name": self.zone.name if self.zone else None,
            "alarm_type": self.alarm_type,
            "level": self.level,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "device_code": self.device_code,
            "handled_by": self.handled_by,
            "handle_note": self.handle_note,
            "occurred_at": (
                self.occurred_at.isoformat() if self.occurred_at else None
            ),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Alarm id={self.id} type={self.alarm_type} status={self.status}>"
