"""
通行日志模型。

AccessLog 记录人脸识别、刷卡、二维码或人工放行产生的通行事件。
它为前端人脸管理页、审计查询和后续告警分析提供基础数据。
"""

from datetime import datetime, timezone

from . import db


def utc_now():
    """返回时区感知的 UTC 时间。"""

    return datetime.now(timezone.utc)


class AccessLog(db.Model):
    """通行日志表。"""

    __tablename__ = "access_log"

    id = db.Column(db.Integer, primary_key=True)

    # 未识别人员也可能产生日志，因此 user_id 可以为空。
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

    # zone_id 指明通行发生的校园区域或门禁点。
    zone_id = db.Column(db.Integer, db.ForeignKey("zone.id"), nullable=False)

    access_method = db.Column(db.String(32), nullable=False, default="face")
    direction = db.Column(db.String(16), nullable=False, default="in")
    result = db.Column(db.String(32), nullable=False, default="granted")
    device_code = db.Column(db.String(64), nullable=True)
    confidence = db.Column(db.Float, nullable=True)
    remark = db.Column(db.String(255), nullable=True)

    occurred_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    user = db.relationship("User", back_populates="access_logs")
    zone = db.relationship("Zone", back_populates="access_logs")

    def to_dict(self):
        """转换为接口响应字典。"""

        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "real_name": self.user.real_name if self.user else None,
            "zone_id": self.zone_id,
            "zone_name": self.zone.name if self.zone else None,
            "access_method": self.access_method,
            "direction": self.direction,
            "result": self.result,
            "device_code": self.device_code,
            "confidence": self.confidence,
            "remark": self.remark,
            "occurred_at": (
                self.occurred_at.isoformat() if self.occurred_at else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<AccessLog id={self.id} result={self.result}>"
