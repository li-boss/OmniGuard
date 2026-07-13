import sys
sys.path.insert(0, '.')
from app import create_app
from models import db, AlarmEvent

app = create_app()
with app.app_context():
    alarms = AlarmEvent.query.order_by(AlarmEvent.created_at.desc()).limit(10).all()
    print('Recent alarms:')
    for a in alarms:
        desc = a.description[:30] if a.description else None
        print(f'  ID={a.id}, type={a.alarm_type}, desc={desc}')