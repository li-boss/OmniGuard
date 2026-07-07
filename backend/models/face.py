from datetime import datetime

from . import db


class RegisteredFace(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    feature_blob = db.Column(db.LargeBinary, nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
