# ==========================
# Flask 基础配置
# ==========================

SECRET_KEY = "smart-campus-alarm-2026-secret"

# ==========================
# 数据库配置
# ==========================

# SQLite 数据库
SQLALCHEMY_DATABASE_URI = "sqlite:///smart_campus.db"
SQLALCHEMY_TRACK_MODIFICATIONS = False

# ==========================
# SocketIO 配置
# ==========================

SOCKET_CORS = "*"

# ==========================
# 钉钉机器人配置
# ==========================

# 请替换成你自己的钉钉机器人 Webhook
DINGTALK_WEBHOOK = (
    "https://oapi.dingtalk.com/robot/send?access_token=替换成你的token"
)