import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.extensions import db


class AlarmFlowTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "DEFAULT_ADMIN_USER": "admin",
            "DEFAULT_ADMIN_PASSWORD": "admin123",
            "JWT_SECRET_KEY": "test-secret",
        })
        self.client = self.app.test_client()
        login = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
        })
        self.headers = {"Authorization": f"Bearer {login.json['data']['token']}"}

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_zone_alarm_handle_flow(self):
        zone = self.client.post("/api/zones", headers=self.headers, json={
            "cameraId": "cam-1",
            "name": "主入口",
            "points": [{"x": 0, "y": 0}, {"x": 100, "y": 0}, {"x": 100, "y": 100}],
        })
        self.assertEqual(zone.status_code, 201)

        alarm = self.client.post("/api/alarms", headers=self.headers, json={
            "cameraId": "cam-1",
            "zoneId": zone.json["data"]["id"],
            "severity": "high",
        })
        self.assertEqual(alarm.status_code, 201)

        handled = self.client.put(
            f"/api/alarms/{alarm.json['data']['id']}/handle",
            headers=self.headers,
            json={"note": "已确认"},
        )
        self.assertEqual(handled.status_code, 200)
        self.assertEqual(handled.json["data"]["status"], "handled")


if __name__ == "__main__":
    unittest.main()
