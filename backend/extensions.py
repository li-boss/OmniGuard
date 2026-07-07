from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO

# 数据库对象
db = SQLAlchemy()

# SocketIO 对象
socketio = SocketIO(
    cors_allowed_origins="*",
)