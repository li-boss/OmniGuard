from datetime import datetime
from . import db

class RegisteredFace(db.Model):
    __tablename__ = "registered_face"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    name = db.Column(db.String(80), nullable=False)
    feature_blob = db.Column(db.LargeBinary, nullable=True)
    feature_data = db.Column(db.Text, nullable=True)
    photo_path = db.Column(db.String(255), nullable=True)
    image_path = db.Column(db.String(255), nullable=True)
    device_code = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(32), nullable=False, default="active")
    last_recognized_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = db.relationship("User", back_populates="faces")

    def to_dict(self, include_feature=True):
        """
        转换为接口响应字典。
        """
        student_id = ""
        if self.user:
            student_id = self.user.username
        else:
            # Fallback if no user relationship, try using user_id
            student_id = str(self.user_id) if self.user_id else ""

        image_preview = f"/api/faces/{self.id}/image" if (self.photo_path or self.image_path) else ""

        data = {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.user.username if self.user else None,
            "real_name": self.user.real_name if self.user else self.name,
            "name": self.name,
            "studentId": student_id,
            "imagePreview": image_preview,
            "image_path": self.image_path or self.photo_path,
            "photo_path": self.photo_path or self.image_path,
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
        return f"<RegisteredFace id={self.id} name={self.name}>"

Face = RegisteredFace
