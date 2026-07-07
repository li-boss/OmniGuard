from datetime import datetime

from . import db


class AlertZone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    camera_id = db.Column(db.String(64), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    polygon = db.Column(db.JSON, nullable=False)
    distance_threshold = db.Column(db.Float, nullable=False, default=0.0)
    stay_seconds = db.Column(db.Integer, nullable=False, default=5)
    enabled = db.Column(db.Boolean, nullable=False, default=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
