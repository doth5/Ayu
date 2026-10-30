"""
Application settings – loaded from .env or environment variables.
"""
from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # ── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "AyuSynk Sales Pipeline"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # ── Database ─────────────────────────────────────────────────────────────
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'ayusynk.db'}"

    # ── API ──────────────────────────────────────────────────────────────────
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8000
    API_BASE_URL: str = "http://127.0.0.1:8000"

    # ── Streamlit ────────────────────────────────────────────────────────────
    STREAMLIT_PORT: int = 8501

    # ── Media ─────────────────────────────────────────────────────────────────
    MEDIA_ROOT: Path = BASE_DIR / "media"
    MAX_UPLOAD_MB: int = 50

    # ── WhatsApp Business API (Meta) — optional alternative ─────────────────
    WHATSAPP_API_URL: str = ""
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # ── WhatsApp Web Automation (Playwright — no external API needed) ────────
    # Set to true to use browser-based WhatsApp Web automation.
    # On first run the browser opens and you scan the QR code once.
    # The session is saved to WA_WEB_SESSION_DIR and reused on restarts.
    WA_WEB_ENABLED: bool = False
    WA_WEB_SESSION_DIR: str = ""  # defaults to <project_root>/wa_session/

    # ── Auto-send control ─────────────────────────────────────────────────────
    # Set to true to have the scheduler send messages automatically.
    # If false, messages are only prepared and shown in the UI queue.
    AUTO_SEND_ENABLED: bool = False

    # Delay (seconds) between consecutive automated sends to avoid rate limits
    AUTO_SEND_DELAY_SECONDS: int = 5

    # ── Scheduler ────────────────────────────────────────────────────────────
    SCHEDULER_TIMEZONE: str = "Asia/Kolkata"

    class Config:
        env_file = str(BASE_DIR / ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
