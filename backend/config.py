import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "development-only")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "120"))
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'smart_campus_security.db'}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_AS_ASCII = False
    FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://127.0.0.1:5173")
    RTMP_BASE_URL = os.getenv("RTMP_BASE_URL", "rtmp://127.0.0.1:1935/live")
    VIDEO_FEED_URL = os.getenv("VIDEO_FEED_URL", "")
    DINGTALK_WEBHOOK = os.getenv("DINGTALK_WEBHOOK", "")
    REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    ALARM_COOLDOWN_SECONDS = int(os.getenv("ALARM_COOLDOWN_SECONDS", "5"))
    ALARM_VIDEO_POST_SECONDS = float(os.getenv("ALARM_VIDEO_POST_SECONDS", "10"))
    ALARM_VIDEO_PRE_SECONDS = float(os.getenv("ALARM_VIDEO_PRE_SECONDS", "5"))
    ALARM_VIDEO_FPS = float(os.getenv("ALARM_VIDEO_FPS", "10"))
    ALARM_VIDEO_QUEUE_SIZE = int(os.getenv("ALARM_VIDEO_QUEUE_SIZE", "300"))
    FACE_MATCH_THRESHOLD = float(os.getenv("FACE_MATCH_THRESHOLD", "0.32"))
    DEFAULT_ADMIN_USER = os.getenv("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
    
    # Audio detection configuration
    AUDIO_SEMANTIC_ENABLED = os.getenv("AUDIO_SEMANTIC_ENABLED", "true").lower() == "true"
    YAMNET_MODEL_URL = os.getenv("YAMNET_MODEL_URL", "https://tfhub.dev/google/yamnet/1")
    AUDIO_CHUNK_SECONDS = float(os.getenv("AUDIO_CHUNK_SECONDS", "0.5"))
    AUDIO_ALARM_COOLDOWN_SECONDS = float(os.getenv("AUDIO_ALARM_COOLDOWN_SECONDS", "30"))
    CAMERA_AUDIO_MONITOR_ENABLED = os.getenv("CAMERA_AUDIO_MONITOR_ENABLED", "false").lower() == "true"
    FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
