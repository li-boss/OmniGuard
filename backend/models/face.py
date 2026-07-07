"""
人脸模型。

Face 用于保存用户的人脸注册数据。课程项目中 feature_data 可以保存
算法模块返回的 JSON 字符串；真实项目中建议加密保存或只保存特征 ID。
"""

from datetime import datetime, timezone

from . import db


def utc_now():
    """返回时区感知的 UTC 时间。"""

    return datetime.now(timezone.utc)


class Face(db.Model):
    """人脸注册表。"""

    __tablename__ = "face"

    id = db.Column(db.Integer, primary_key=True)

    # 人脸所属用户。一个用户可以绑定多条人脸记录。
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # 图片路径可以是本地路径、对象存储 URL 或前端上传后的文件标识。
    image_path = db.Column(db.String(255), nullable=True)

    # 算法特征数据。为方便 D 模块读取，使用 Text 保存 JSON 字符串。
    feature_data = db.Column(db.Text, nullable=False)

    # 设备或摄像头编号，用于记录该人脸由哪个采集端注册。
    device_code = db.Column(db.String(64), nullable=True)

    # active 表示可用于识别；disabled 表示保留数据但不参与识别。
    status = db.Column(db.String(32), nullable=False, default="active")

    last_recognized_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user = db.relationship("User", back_populates="faces")

    def to_dict(self, include_feature=True):
        """
        转换为接口响应字典。

        include_feature=False 时不返回 feature_data，适合普通列表页；
        D 模块进行人脸比对时可以请求包含特征数据。
        """

        data = {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "real_name": self.user.real_name if self.user else None,
            "image_path": self.image_path,
            "device_code": self.device_code,
            "status": self.status,
            "last_recognized_at": (
                self.last_recognized_at.isoformat()
                if self.last_recognized_at
                else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_feature:
            data["feature_data"] = self.feature_data
        return data

    def __repr__(self):
        return f"<Face id={self.id} user_id={self.user_id}>"
