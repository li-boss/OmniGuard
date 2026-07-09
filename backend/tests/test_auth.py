import sys
import unittest
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.extensions import db


class AuthTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "DEFAULT_ADMIN_USER": "admin",
            "DEFAULT_ADMIN_PASSWORD": "admin123",
            "JWT_SECRET_KEY": "test-secret",
        })
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self):
        result = self.client.post("/api/auth/login", json={
            "username": "admin",
            "password": "admin123",
        })
        return result.json["data"]["token"]

    def test_login_and_me(self):
        token = self.login()
        result = self.client.get("/api/users/me", headers={
            "Authorization": f"Bearer {token}",
        })
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["data"]["username"], "admin")

    def test_duplicate_register_returns_409(self):
        result = self.client.post("/api/auth/register", json={
            "username": "admin",
            "password": "admin123",
        })
        self.assertEqual(result.status_code, 409)


if __name__ == "__main__":
    unittest.main()
