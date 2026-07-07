"""
数据库模型包初始化。

这里创建全项目唯一的 SQLAlchemy 对象，并集中导入所有模型。
manage.py 调用 db.create_all() 时，必须确保模型已经被导入，
否则 SQLAlchemy 不知道要创建哪些表。
"""

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


# noqa: E402 表示这些导入必须放在 db 创建之后，避免循环导入。
from .user import User  # noqa: E402,F401
from .face import Face  # noqa: E402,F401
from .zone import Zone  # noqa: E402,F401
from .access_log import AccessLog  # noqa: E402,F401
from .alarm import Alarm  # noqa: E402,F401
