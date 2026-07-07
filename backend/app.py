"""
校园安防系统 C 模块启动入口。
"""

import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from backend.api import register_blueprints
from backend.config import get_config
from backend.models import db

try:
    from flask_cors import CORS
except ImportError:
    CORS = None


def create_app(config_object=None):
    """创建 Flask 应用实例。"""

    app = Flask(__name__)
    app.config.from_object(config_object or get_config())
    db.init_app(app)

    if CORS:
        CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    register_blueprints(app)

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        """将 Flask 默认 HTML 错误页转换为统一 JSON。"""

        return jsonify(
            {
                "code": error.code,
                "message": error.description or error.name,
                "data": {},
            }
        ), error.code

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        """数据库异常兜底，避免泄露堆栈。"""

        db.session.rollback()
        return jsonify({"code": 500, "message": "数据库操作失败", "data": {}}), 500

    @app.get("/")
    def index():
        """服务健康检查接口。"""

        return jsonify(
            {
                "code": 200,
                "message": "校园安防系统 C 模块服务运行中",
                "data": {"module": "auth-user-face"},
            }
        )

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
