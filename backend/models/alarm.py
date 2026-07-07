from datetime import datetime

from . import db


class AlarmEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    alarm_type = db.Column(db.String(64), nullable=False)
    level = db.Column(db.String(32), nullable=False, default="medium")
    camera_id = db.Column(db.String(64), nullable=False, index=True)
    coordinate = db.Column(db.JSON, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="pending")
    snapshot_path = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    handled_at = db.Column(db.DateTime, nullable=True)
