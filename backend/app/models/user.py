from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    real_name = db.Column(db.String(64), nullable=True)
    role = db.Column(db.String(32), nullable=False, default="operator")
    phone = db.Column(db.String(32), nullable=True)
    department = db.Column(db.String(128), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "realName": self.real_name,
            "real_name": self.real_name,
            "role": self.role,
            "phone": self.phone,
            "department": self.department,
            "isActive": self.is_active,
            "is_active": self.is_active,
            "createdAt": self.created_at.isoformat(),
            "created_at": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
