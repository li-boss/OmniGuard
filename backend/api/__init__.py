"""
API 蓝图注册入口。

C 模块包含三组接口：
1. user_api：登录、注册、当前用户、用户管理。
2. face_api：人脸注册、查询、删除、特征列表。
3. log_api：通行日志查询和写入。
"""

from backend.api.face_api import face_bp
from backend.api.log_api import log_bp
from backend.api.user_api import user_bp


def register_blueprints(app):
    """统一注册 C 模块蓝图。"""

    app.register_blueprint(user_bp)
    app.register_blueprint(face_bp)
    app.register_blueprint(log_bp)
