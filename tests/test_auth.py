"""
C 模块自动测试。
"""

import pytest

from backend.app import create_app
from backend.config import TestingConfig
from backend.models import Face, User, Zone, db


@pytest.fixture()
def app():
    """创建使用内存数据库的测试应用。"""

    test_app = create_app(TestingConfig)
    with test_app.app_context():
        db.create_all()

        admin = User(username="admin", real_name="管理员", role="admin")
        admin.set_password("123456")
        student = User(username="student01", real_name="学生一号", role="student")
        student.set_password("123456")
        zone = Zone(name="测试门禁", code="TEST-GATE-001")
        db.session.add_all([admin, student, zone])
        db.session.commit()

        yield test_app

        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    """Flask 测试客户端。"""

    return app.test_client()


def login(client, username="admin", password="123456"):
    """登录并返回完整响应 data。"""

    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()["data"]


def auth_headers(token):
    """生成 Bearer token 请求头。"""

    return {"Authorization": f"Bearer {token}"}


def test_register_login_and_profile(client):
    response = client.post(
        "/api/auth/register",
        json={
            "username": "security01",
            "password": "123456",
            "real_name": "保安一号",
            "role": "security",
        },
    )
    assert response.status_code == 201

    data = login(client, "security01", "123456")
    profile = client.get("/api/users/me", headers=auth_headers(data["access_token"]))
    assert profile.status_code == 200
    assert profile.get_json()["data"]["user"]["username"] == "security01"


def test_duplicate_register_returns_409(client):
    payload = {
        "username": "repeat01",
        "password": "123456",
        "name": "重复用户",
        "role": "student",
        "department": "计算机学院",
    }
    first = client.post("/api/auth/register", json=payload)
    second = client.post("/api/auth/register", json=payload)

    assert first.status_code == 201
    assert second.status_code == 409


def test_protected_api_requires_token(client):
    response = client.get("/api/users/me")
    assert response.status_code == 401


def test_non_admin_access_user_list_returns_403(client):
    data = login(client, "student01", "123456")

    response = client.get("/api/users", headers=auth_headers(data["access_token"]))
    assert response.status_code == 403


def test_refresh_requires_refresh_token(client):
    data = login(client)

    access_response = client.post(
        "/api/auth/refresh",
        headers=auth_headers(data["access_token"]),
    )
    refresh_response = client.post(
        "/api/auth/refresh",
        headers=auth_headers(data["refresh_token"]),
    )

    assert access_response.status_code == 401
    assert refresh_response.status_code == 200
    assert refresh_response.get_json()["data"]["access_token"]


def test_change_password(client):
    data = login(client)
    response = client.put(
        "/api/users/me/password",
        headers=auth_headers(data["access_token"]),
        json={"old_password": "123456", "new_password": "654321"},
    )
    assert response.status_code == 200

    new_data = login(client, "admin", "654321")
    assert new_data["access_token"]


def test_face_register_list_delete(client):
    data = login(client)

    response = client.post(
        "/api/faces/register",
        headers=auth_headers(data["access_token"]),
        json={
            "user_id": 1,
            "face_image_url": "/uploads/faces/admin.jpg",
            "face_encoding": "[0.12, 0.34, 0.56]",
            "device_code": "camera-test",
        },
    )
    assert response.status_code == 201
    face_id = response.get_json()["data"]["face"]["id"]

    response = client.get("/api/faces", headers=auth_headers(data["access_token"]))
    assert response.status_code == 200
    assert response.get_json()["data"]["total"] == 1

    response = client.delete(
        f"/api/faces/{face_id}",
        headers=auth_headers(data["access_token"]),
    )
    assert response.status_code == 200


def test_face_permission_and_json_404(client, app):
    student_data = login(client, "student01", "123456")

    response = client.post(
        "/api/faces/register",
        headers=auth_headers(student_data["access_token"]),
        json={
            "user_id": 1,
            "face_encoding": "[0.1, 0.2]",
            "face_image_url": "/uploads/admin.jpg",
        },
    )
    assert response.status_code == 403

    with app.app_context():
        face = Face(user_id=1, feature_data="[0.1]", image_path="/uploads/admin.jpg")
        db.session.add(face)
        db.session.commit()
        face_id = face.id

    response = client.delete(
        f"/api/faces/{face_id}",
        headers=auth_headers(student_data["access_token"]),
    )
    assert response.status_code == 403

    response = client.delete(
        "/api/faces/9999",
        headers=auth_headers(student_data["access_token"]),
    )
    assert response.status_code == 404
    assert response.is_json
    assert response.get_json()["code"] == 404


def test_create_and_list_access_log(client):
    data = login(client)

    response = client.post(
        "/api/access-logs",
        headers=auth_headers(data["access_token"]),
        json={
            "user_id": 1,
            "zone_id": 1,
            "access_method": "face",
            "direction": "in",
            "result": "granted",
            "device_code": "camera-test",
            "confidence": 0.96,
        },
    )
    assert response.status_code == 201

    response = client.get(
        "/api/access-logs",
        headers=auth_headers(data["access_token"]),
    )
    assert response.status_code == 200
    assert response.get_json()["data"]["total"] == 1


def test_five_continuous_calls_have_no_500(client):
    data = login(client)

    for _ in range(5):
        response = client.get(
            "/api/users/me",
            headers=auth_headers(data["access_token"]),
        )
        assert response.status_code == 200
        assert response.status_code != 500
