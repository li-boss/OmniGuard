"""
用户模型。

User 是 C 模块的核心模型，负责保存登录账号、用户角色和基础资料。
密码只保存哈希值，严禁保存明文密码。
"""

from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from . import db


def utc_now():
    """返回时区感知的 UTC 时间。"""

    return datetime.now(timezone.utc)


class User(db.Model):
    """系统用户表。"""

    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    # 登录账号，必须唯一。前端登录页使用该字段登录。
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)

    # 密码哈希。通过 set_password 写入，通过 check_password 校验。
    password_hash = db.Column(db.String(255), nullable=False)

    # 真实姓名、角色、手机号用于后台展示和权限控制。
    real_name = db.Column(db.String(64), nullable=True)
    role = db.Column(db.String(32), nullable=False, default="security")
    phone = db.Column(db.String(32), nullable=True)
    department = db.Column(db.String(128), nullable=True)

    # 禁用账号后，该用户不能继续登录或访问受保护接口。
    is_active = db.Column(db.Boolean, nullable=False, default=True)

    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    faces = db.relationship(
        "Face",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy=True,
    )
    access_logs = db.relationship("AccessLog", back_populates="user", lazy=True)

    def set_password(self, raw_password):
        """将明文密码转换为安全哈希后保存。"""

        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        """校验明文密码是否与哈希匹配。"""

        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        """转换为接口响应字典，不返回 password_hash。"""

        return {
            "id": self.id,
            "username": self.username,
            "real_name": self.real_name,
            "role": self.role,
            "phone": self.phone,
            "department": self.department,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f"<User id={self.id} username={self.username}>"
