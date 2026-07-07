from flask import Blueprint

# 告警接口
event_bp = Blueprint(
    "event",
    __name__,
    url_prefix="/api/alarms"
)

# 仪表盘接口
dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/api/dashboard"
)

# 导入路由（放在最后，避免循环导入）
from . import event_api
from . import dashboard_api