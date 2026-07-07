import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///{}".format(BASE_DIR / "smart_campus_security.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RTMP_URL = os.getenv("RTMP_URL", "")
    DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
