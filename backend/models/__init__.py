from app.extensions import db
from app.models import AccessLog, AlarmEvent, FaceRecord, User, Zone

AlertZone = Zone
RegisteredFace = FaceRecord

__all__ = [
    "AccessLog",
    "AlarmEvent",
    "AlertZone",
    "FaceRecord",
    "RegisteredFace",
    "User",
    "Zone",
    "db",
]
