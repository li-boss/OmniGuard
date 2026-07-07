from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

from .alarm import AlarmEvent  # noqa: E402,F401
from .face import RegisteredFace  # noqa: E402,F401
from .user import User  # noqa: E402,F401
from .zone import AlertZone  # noqa: E402,F401
