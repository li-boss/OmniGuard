"""
数据库管理脚本。

运行方式：
    python -m backend.manage

脚本会完成：
1. 创建所有 ORM 模型对应的数据表。
2. 初始化默认管理员。
3. 初始化一个默认校园区域，方便 AccessLog API 直接测试。
"""

import os
import sys

# 兼容在 backend 目录中直接执行 python manage.py。
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import create_app
from backend.models import User, Zone, db


def create_tables():
    """创建数据表并写入基础演示数据。"""

    app = create_app()
    with app.app_context():
        db.create_all()

        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                real_name="系统管理员",
                role="admin",
                phone="13800000000",
                is_active=True,
            )
            admin.set_password("123456")
            db.session.add(admin)

        default_zone = Zone.query.filter_by(code="GATE-001").first()
        if not default_zone:
            default_zone = Zone(
                name="校园东门",
                code="GATE-001",
                zone_type="gate",
                location="学校东侧主入口",
                risk_level="medium",
            )
            db.session.add(default_zone)

        db.session.commit()
        print("数据表创建完成")
        print("默认管理员：admin / 123456")
        print("默认区域：GATE-001 校园东门")


if __name__ == "__main__":
    create_tables()
