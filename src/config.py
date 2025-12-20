import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
    # App version (bump this to bust static file caches)
    VERSION = "1.1.0"

    # Base paths
    BASE_DIR = Path(__file__).parent.parent

    # Gemini API
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Available models
    MODELS = {
        "gemini-3-flash-preview": "Gemini 3 Flash (Fast)",
        "gemini-3-pro-preview": "Gemini 3 Pro (Advanced)",
    }
    DEFAULT_MODEL = "gemini-3-flash-preview"

    # Google Identity Services (GIS) - only Client ID needed
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24 * 7  # 1 week

    # Email whitelist
    ALLOWED_EMAILS: list[str] = [
        email.strip() for email in os.getenv("ALLOWED_EMAILS", "").split(",") if email.strip()
    ]

    # Local mode (skip auth)
    LOCAL_MODE: bool = os.getenv("LOCAL_MODE", "false").lower() == "true"

    # Server
    PORT: int = int(os.getenv("PORT", "8000"))
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    DEBUG: bool = FLASK_ENV == "development"

    # Database
    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "chatbot.db")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of errors."""
        errors: list[str] = []

        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")

        if not cls.LOCAL_MODE:
            if not cls.GOOGLE_CLIENT_ID:
                errors.append("GOOGLE_CLIENT_ID is required (or set LOCAL_MODE=true)")
            if not cls.ALLOWED_EMAILS:
                errors.append("ALLOWED_EMAILS is required (or set LOCAL_MODE=true)")

        if cls.JWT_SECRET_KEY == "dev-secret-change-me" and not cls.LOCAL_MODE:
            errors.append("JWT_SECRET_KEY must be set to a secure value in production")

        return errors
