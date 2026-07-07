"""
项目配置文件。

集中管理数据库、JWT、CORS 和运行环境配置。
"""

import os
from datetime import timedelta

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


class Config:
    """所有环境共享的基础配置。"""

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "campus-security-flask-secret")
    JWT_SECRET_KEY = os.getenv(
        "JWT_SECRET_KEY",
        "campus-security-jwt-secret-change-me-32bytes-min",
    )

    JWT_EXPIRES_DELTA = timedelta(
        seconds=int(os.getenv("JWT_EXPIRES_SECONDS", "7200"))
    )
    JWT_REFRESH_EXPIRES_DELTA = timedelta(
        seconds=int(os.getenv("JWT_REFRESH_EXPIRES_SECONDS", "604800"))
    )

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(BASE_DIR, "campus_security.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False

    CORS_ORIGINS = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")


class DevelopmentConfig(Config):
    """开发环境配置。"""

    DEBUG = True


class TestingConfig(Config):
    """单元测试配置。"""

    TESTING = True
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    JWT_EXPIRES_DELTA = timedelta(minutes=30)
    JWT_REFRESH_EXPIRES_DELTA = timedelta(days=7)


class ProductionConfig(Config):
    """生产环境配置。"""

    DEBUG = False


def get_config():
    """根据 FLASK_ENV 返回配置类。"""

    env = os.getenv("FLASK_ENV", "development").lower()
    if env == "testing":
        return TestingConfig
    if env == "production":
        return ProductionConfig
    return DevelopmentConfig
