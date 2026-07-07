"""
校园区域模型。

Zone 由 D 模块围栏配置接口继续维护，但 C 模块先统一定义模型，
确保 AccessLog、Alarm 等表的外键可以正常创建。
"""

from datetime import datetime, timezone

from . import db


def utc_now():
    """返回时区感知的 UTC 时间。"""

    return datetime.now(timezone.utc)


class Zone(db.Model):
    """校园区域表。"""

    __tablename__ = "zone"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    code = db.Column(db.String(64), unique=True, nullable=False, index=True)
    zone_type = db.Column(db.String(32), nullable=False, default="gate")
    location = db.Column(db.String(255), nullable=True)
    risk_level = db.Column(db.String(32), nullable=False, default="low")
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    access_logs = db.relationship("AccessLog", back_populates="zone", lazy=True)
    alarms = db.relationship("Alarm", back_populates="zone", lazy=True)

    def to_dict(self):
        """转换为接口响应字典。"""

        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "zone_type": self.zone_type,
            "location": self.location,
            "risk_level": self.risk_level,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<Zone id={self.id} code={self.code}>"
