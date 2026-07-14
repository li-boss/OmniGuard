from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .alarm import AlarmEvent  # noqa: E402,F401
from .face import RegisteredFace, Face  # noqa: E402,F401
from .user import User  # noqa: E402,F401
from .zone import AlertZone  # noqa: E402,F401
from .access_log import AccessLog  # noqa: E402,F401
from .daily_report import DailyReport  # noqa: E402,F401
