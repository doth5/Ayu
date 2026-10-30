"""
Application settings – loaded from .env or environment variables.
"""
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── App ────────────────────────────────────────────────────────────────
    APP_NAME: str = "AyuSynk Sales Pipeline"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'ayusynk.db'}"

    # ── API ───────────────────────────────────────────────────────────────
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_BASE_URL: str = "http://127.0.0.1:8000"

    # ── Streamlit ─────────────────────────────────────────────────────────
    STREAMLIT_PORT: int = 8501

    # ── Media ─────────────────────────────────────────────────────────────
    MEDIA_ROOT: Path = BASE_DIR / "media"
    MAX_UPLOAD_MB: int = 50

    # ── WhatsApp Business API (Meta) — optional alternative ─────────────
    WHATSAPP_API_URL: str = ""
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # ── WhatsApp Web Automation (Playwright — no external API needed) ─────
    WA_WEB_ENABLED: bool = False
    WA_WEB_SESSION_DIR: str = ""

    # ── Auto-send control ─────────────────────────────────────────────────
    AUTO_SEND_ENABLED: bool = False
    AUTO_SEND_DELAY_SECONDS: int = 5

    # ── Scheduler ───────────────────────────────────────────────────────────
    SCHEDULER_TIMEZONE: str = "Asia/Kolkata"

    # ── Reliability contract configuration ─────────────────────────────────
    AUTOMATION_ENABLED: bool = True
    GLOBAL_EMERGENCY_STOP: bool = False
    WORKER_CONCURRENCY: int = 4
    TASK_LEASE_SECONDS: int = 300
    TASK_HEARTBEAT_SECONDS: int = 60
    MAX_ACTION_ATTEMPTS: int = 5
    MAX_RECOVERY_ATTEMPTS: int = 6
    MAX_RECOVERY_DURATION_SECONDS: int = 1800
    MAX_AI_RECOVERY_CALLS: int = 3
    RECOVERY_REVIEW_THRESHOLD: int = 3
    PROVIDER_REQUEST_TIMEOUT_SECONDS: int = 30
    PROVIDER_RECONCILIATION_TIMEOUT_SECONDS: int = 120
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 5
    CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 60

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
