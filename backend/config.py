import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


class Config:
    # Security
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret")

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///{}".format(BASE_DIR / "smart_campus_security.db"),
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # External services
    RTMP_URL = os.getenv("RTMP_URL", "")
    DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    ALARM_COOLDOWN_SECONDS = int(os.getenv("ALARM_COOLDOWN_SECONDS", "30"))

    # CORS — allow the frontend dev server to call APIs
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    CORS_METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    CORS_ALLOW_HEADERS = ["Content-Type", "Authorization"]

    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "omniguard.log"))
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))  # 10 MB
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))


def setup_logging(app):
    """Configure rotating file handler + console handler for the Flask app."""
    log_level = getattr(logging, app.config["LOG_LEVEL"], logging.INFO)

    # Ensure log directory exists
    log_path = Path(app.config["LOG_FILE"])
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # File handler (rotating)
    file_handler = RotatingFileHandler(
        str(log_path),
        maxBytes=app.config["LOG_MAX_BYTES"],
        backupCount=app.config["LOG_BACKUP_COUNT"],
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    ))

    # Attach handlers to app logger
    app.logger.addHandler(file_handler)
    app.logger.addHandler(console_handler)
    app.logger.setLevel(log_level)

    # Also set Flask's root logger
    flask_logger = logging.getLogger("flask.app")
    flask_logger.addHandler(file_handler)
    flask_logger.addHandler(console_handler)
    flask_logger.setLevel(log_level)

    app.logger.info("Logging configured — level=%s, file=%s", log_level, log_path)
