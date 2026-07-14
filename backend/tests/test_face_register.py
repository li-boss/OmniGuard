import sys
import unittest
import base64
import json
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from models import db, User, Face, AlertZone

# 1x1 pixel base64 encoded JPEG
DUMMY_BASE64_IMAGE = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAIBAQEBAQIBAQECAgICAgQDAgICAgUEBAMEBgUGBgYFBgYGBwkIBgcJBwYGCAsICQoKCgoKBggLDAsKDAkKCgr/2wBDAQICAgICAgUDAwUKBwYHCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgr/wAARCAAKAAoDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD9/KKKKAP/2Q=="

class FaceRegisterTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "DEFAULT_ADMIN_USER": "admin",
            "DEFAULT_ADMIN_PASSWORD": "admin123",
            "JWT_SECRET_KEY": "test-secret",
        })
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, username="admin", password="admin123"):
        result = self.client.post("/api/auth/login", json={
            "username": username,
            "password": password,
        })
        return result.json["data"]["token"]

    def test_face_lifecycle(self):
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        # 1. 列表初始为空
        res = self.client.get("/api/faces", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json["data"]), 0)

        # 2. 录入人脸并自动创建用户 (学号 20210001, 姓名 张三)
        res = self.client.post("/api/faces/register", headers=headers, json={
            "studentId": "20210001",
            "name": "张三",
            "image": DUMMY_BASE64_IMAGE,
        })
        self.assertEqual(res.status_code, 201, msg=f"Register face failed: {res.json}")
        self.assertIn("人脸注册成功", res.json["message"])
        self.assertIn("123456", res.json["message"]) # 提示默认密码

        face_id = res.json["data"]["face"]["id"]

        # 3. 验证用户是否被成功自动创建
        user = User.query.filter_by(username="20210001").first()
        self.assertIsNotNone(user)
        self.assertEqual(user.real_name, "张三")
        self.assertTrue(user.check_password("123456"))

        # 4. 获取人脸列表，验证非空
        res = self.client.get("/api/faces", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json["data"]), 1)
        self.assertEqual(res.json["data"][0]["name"], "张三")
        self.assertEqual(res.json["data"][0]["studentId"], "20210001")

        # 5. 下载人脸图片
        res = self.client.get(f"/api/faces/{face_id}/image")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.mimetype, "image/jpeg")
        res.close()

        # 6. 删除人脸并确认
        res = self.client.delete(f"/api/faces/{face_id}", headers=headers)
        self.assertEqual(res.status_code, 200)
        
        # 列表应重新为空
        res = self.client.get("/api/faces", headers=headers)
        self.assertEqual(len(res.json["data"]), 0)

    def test_access_log_lifecycle(self):
        token = self.login()
        headers = {"Authorization": f"Bearer {token}"}

        # 1. 创建防区用于测试
        zone = AlertZone(name="主校门", camera_id="cam_01", polygon=[[0,0], [1,0], [1,1], [0,1]])
        db.session.add(zone)
        db.session.commit()

        # 2. 写入通行日志
        res = self.client.post("/api/access-logs", headers=headers, json={
            "zone_id": zone.id,
            "access_method": "face",
            "direction": "in",
            "result": "granted",
            "confidence": 0.95,
            "remark": "测试刷脸通行"
        })
        self.assertEqual(res.status_code, 201)
        log_id = res.json["data"]["log"]["id"]

        # 3. 分页查询通行日志
        res = self.client.get("/api/access-logs", headers=headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json["data"]["total"], 1)
        self.assertEqual(res.json["data"]["items"][0]["zone_name"], "主校门")
        self.assertEqual(res.json["data"]["items"][0]["remark"], "测试刷脸通行")

if __name__ == "__main__":
    unittest.main()
