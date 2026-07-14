import time
import unittest

from app import create_app
from core_cv.pipeline import CameraPipeline
from models import AccessLog, RegisteredFace, User, db


class AccessLogIntegrationTest(unittest.TestCase):
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

        self.student = User(username="student01", role="student", real_name="学生一")
        self.student.set_password("password123")
        self.other_student = User(username="student02", role="student", real_name="学生二")
        self.other_student.set_password("password123")
        db.session.add_all([self.student, self.other_student])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self, username, password):
        response = self.client.post("/api/auth/login", json={
            "username": username,
            "password": password,
        })
        return {"Authorization": f"Bearer {response.json['data']['token']}"}

    def test_access_log_route_is_unique_and_pagination_uses_page_size(self):
        matching_rules = [
            rule for rule in self.app.url_map.iter_rules()
            if rule.rule == "/api/access-logs" and "GET" in rule.methods
        ]
        self.assertEqual(len(matching_rules), 1)
        self.assertEqual(matching_rules[0].endpoint, "access_log.list_access_logs")

        db.session.add_all([
            AccessLog(user_id=self.student.id, device_code="cam-1")
            for _ in range(60)
        ])
        db.session.commit()
        headers = self._login("admin", "admin123")

        response_10 = self.client.get("/api/access-logs?page=1&pageSize=10", headers=headers)
        response_50 = self.client.get("/api/access-logs?page=1&pageSize=50", headers=headers)

        self.assertEqual(response_10.status_code, 200)
        self.assertEqual(len(response_10.json["data"]["items"]), 10)
        self.assertEqual(response_10.json["data"]["pageSize"], 10)
        self.assertEqual(response_50.status_code, 200)
        self.assertEqual(len(response_50.json["data"]["items"]), 50)
        self.assertEqual(response_50.json["data"]["pageSize"], 50)

    def test_student_read_scope_and_delete_permissions(self):
        own_log = AccessLog(user_id=self.student.id, device_code="cam-1")
        other_log = AccessLog(user_id=self.other_student.id, device_code="cam-2")
        db.session.add_all([own_log, other_log])
        db.session.commit()
        own_id = own_log.id
        other_id = other_log.id

        student_headers = self._login("student01", "password123")
        list_response = self.client.get("/api/access-logs", headers=student_headers)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual([item["id"] for item in list_response.json["data"]["items"]], [own_id])

        forbidden_list = self.client.get(
            f"/api/access-logs?user_id={self.other_student.id}",
            headers=student_headers,
        )
        self.assertEqual(forbidden_list.status_code, 403)
        self.assertEqual(
            self.client.get(f"/api/access-logs/{other_id}", headers=student_headers).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(f"/api/access-logs/{own_id}", headers=student_headers).status_code,
            403,
        )

        admin_headers = self._login("admin", "admin123")
        self.assertEqual(
            self.client.get(f"/api/access-logs/{other_id}", headers=admin_headers).status_code,
            200,
        )
        self.assertEqual(
            self.client.delete(f"/api/access-logs/{other_id}", headers=admin_headers).status_code,
            200,
        )

    def test_recognition_writes_real_user_id_and_short_term_deduplicates(self):
        face = RegisteredFace(user_id=self.student.id, name="学生一")
        db.session.add(face)
        db.session.commit()

        pipeline = object.__new__(CameraPipeline)
        pipeline.app = self.app
        pipeline.camera_id = "cam-1"
        pipeline._last_access_log_at = {}
        pipeline._access_log_cooldown_seconds = 10.0

        pipeline._record_recognized_access(self.student.id, zone_id=None, confidence=0.91)
        pipeline._record_recognized_access(self.student.id, zone_id=None, confidence=0.92)

        logs = AccessLog.query.filter_by(user_id=self.student.id).all()
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].user_id, self.student.id)
        self.assertEqual(logs[0].device_code, "cam-1")
        self.assertAlmostEqual(logs[0].confidence, 0.91)
        db.session.refresh(face)
        self.assertIsNotNone(face.last_recognized_at)

        pipeline._last_access_log_at[self.student.id] = time.monotonic() - 11.0
        pipeline._record_recognized_access(self.student.id, zone_id=None, confidence=0.93)
        self.assertEqual(AccessLog.query.filter_by(user_id=self.student.id).count(), 2)


if __name__ == "__main__":
    unittest.main()
