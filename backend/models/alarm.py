from datetime import datetime, timedelta
from backend.app import db


class AlarmEvent(db.Model):
    __tablename__ = 'alarm_events'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type = db.Column(db.String(50), nullable=False, comment='intrusion / face_unknown / face_known / loitering')
    severity = db.Column(db.String(20), nullable=False, default='medium', comment='low / medium / high / critical')
    camera_id = db.Column(db.String(100), nullable=False)
    zone_id = db.Column(db.Integer, nullable=True)
    snapshot_url = db.Column(db.String(500), nullable=True)
    clip_url = db.Column(db.String(500), nullable=True)
    description = db.Column(db.Text, nullable=True)
    detection_data = db.Column(db.JSON, nullable=True, comment='raw detection result from CV pipeline')
    status = db.Column(db.String(20), nullable=False, default='pending', comment='pending / handling / resolved / false_positive')
    handler_id = db.Column(db.Integer, nullable=True)
    handle_note = db.Column(db.Text, nullable=True)
    handle_time = db.Column(db.DateTime, nullable=True)
    escalation_level = db.Column(db.Integer, nullable=False, default=0, comment='0=normal, 1=supervisor, 2=admin')
    escalation_deadline = db.Column(db.DateTime, nullable=True, comment='timeout for current escalation level')
    dingtalk_notified = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    SEVERITY_ORDER = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
    ESCALATION_TIMEOUTS = {
        0: None,
        1: 600,
        2: 300,
    }

    def to_dict(self):
        return {
            'id': self.id,
            'type': self.type,
            'severity': self.severity,
            'camera_id': self.camera_id,
            'zone_id': self.zone_id,
            'snapshot_url': self.snapshot_url,
            'clip_url': self.clip_url,
            'description': self.description,
            'detection_data': self.detection_data,
            'status': self.status,
            'handler_id': self.handler_id,
            'handle_note': self.handle_note,
            'handle_time': self.handle_time.isoformat() if self.handle_time else None,
            'escalation_level': self.escalation_level,
            'escalation_deadline': self.escalation_deadline.isoformat() if self.escalation_deadline else None,
            'dingtalk_notified': self.dingtalk_notified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def should_escalate(self):
        if self.status in ('resolved', 'false_positive'):
            return False
        if self.escalation_deadline and datetime.utcnow() > self.escalation_deadline:
            return True
        return False

    def escalate(self):
        next_level = self.escalation_level + 1
        if next_level > 2:
            return False
        self.escalation_level = next_level
        timeout_seconds = self.ESCALATION_TIMEOUTS.get(next_level, 300)
        if timeout_seconds:
            self.escalation_deadline = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        return True
