from sqlalchemy import inspect, text

from models import db


def ensure_alarm_video_path_column():
    """Add the nullable replay column to existing databases without altering old data."""
    inspector = inspect(db.engine)
    if "alarm_events" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("alarm_events")}
    if "video_path" not in columns:
        db.session.execute(text("ALTER TABLE alarm_events ADD COLUMN video_path VARCHAR(500)"))
        db.session.commit()
    if "triggered_at" not in columns:
        db.session.execute(text("ALTER TABLE alarm_events ADD COLUMN triggered_at DATETIME"))
        db.session.commit()
