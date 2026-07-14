from datetime import datetime
from models import db


class DailyReport(db.Model):
    __tablename__ = 'daily_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, default='校园安全日报')
    generated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    summary = db.Column(db.String(200), nullable=False)
    risk_score = db.Column(db.Integer, nullable=False, default=0)
    risk_level = db.Column(db.String(20), nullable=False, default='低')
    
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    
    total_alarms = db.Column(db.Integer, default=0)
    critical_alarms = db.Column(db.Integer, default=0)
    high_alarms = db.Column(db.Integer, default=0)
    medium_alarms = db.Column(db.Integer, default=0)
    low_alarms = db.Column(db.Integer, default=0)
    
    json_path = db.Column(db.String(255), nullable=False)
    pdf_path = db.Column(db.String(255), nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'generated_at': self.generated_at.isoformat() + 'Z' if self.generated_at else None,
            'summary': self.summary,
            'risk_score': self.risk_score,
            'risk_level': self.risk_level,
            'start_time': self.start_time.isoformat() + 'Z' if self.start_time else None,
            'end_time': self.end_time.isoformat() + 'Z' if self.end_time else None,
            'total_alarms': self.total_alarms,
            'critical_alarms': self.critical_alarms,
            'high_alarms': self.high_alarms,
            'medium_alarms': self.medium_alarms,
            'low_alarms': self.low_alarms,
            'json_path': self.json_path,
            'pdf_path': self.pdf_path,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None
        }
    
    @staticmethod
    def calculate_risk_score(critical_count, high_count, medium_count, low_count):
        score = critical_count * 10 + high_count * 7 + medium_count * 4 + low_count * 1
        return min(score, 100)
    
    @staticmethod
    def get_risk_level(score):
        if score <= 30:
            return '低'
        elif score <= 60:
            return '中'
        else:
            return '高'