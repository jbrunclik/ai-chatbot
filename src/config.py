import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Config:
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

    # Image generation model
    IMAGE_GENERATION_MODEL = "gemini-3-pro-image-preview"
    MAX_IMAGE_PROMPT_LENGTH: int = int(os.getenv("MAX_IMAGE_PROMPT_LENGTH", "2000"))  # characters

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

    # Server
    PORT: int = int(os.getenv("PORT", "8000"))
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    GUNICORN_WORKERS: int = int(os.getenv("GUNICORN_WORKERS", "2"))
    GUNICORN_TIMEOUT: int = int(os.getenv("GUNICORN_TIMEOUT", "300"))  # 5 minutes default
    SSE_KEEPALIVE_INTERVAL: int = int(os.getenv("SSE_KEEPALIVE_INTERVAL", "15"))  # seconds

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Cost tracking
    COST_CURRENCY: str = os.getenv("COST_CURRENCY", "CZK").upper()  # Default to CZK

    # Gemini 3 pricing (per million tokens) - as of Dec 2025
    # These should be updated when Google changes pricing
    MODEL_PRICING = {
        "gemini-3-flash-preview": {
            "input": 0.075,  # $0.075 per million input tokens
            "output": 0.30,  # $0.30 per million output tokens
        },
        "gemini-3-pro-preview": {
            "input": 1.25,  # $1.25 per million input tokens
            "output": 5.00,  # $5.00 per million output tokens
        },
        "gemini-3-pro-image-preview": {
            "input": 2.00,  # $2.00 per million input tokens (text prompts)
            "output": 12.00,  # $12.00 per million output tokens (images + thinking)
        },
        "gemini-2.0-flash": {
            "input": 0.075,  # Used for title generation
            "output": 0.30,
        },
    }

    # Currency conversion rates (USD to other currencies)
    # These should be updated regularly - see TODO.md for automated update task
    CURRENCY_RATES = {
        "USD": 1.0,
        "CZK": 23.0,  # Approximate rate - should be updated regularly
        "EUR": 0.92,
        "GBP": 0.79,
    }

    @classmethod
    def is_development(cls) -> bool:
        """Check if running in development mode."""
        return cls.FLASK_ENV == "development"

    @classmethod
    def is_testing(cls) -> bool:
        """Check if running in testing mode."""
        return cls.FLASK_ENV == "testing"

    @classmethod
    def is_e2e_testing(cls) -> bool:
        """Check if running in E2E testing mode (browser tests with mocked backend).

        E2E tests set E2E_TESTING=true to enable auth bypass while still
        using FLASK_ENV=testing for other test-specific behavior.
        """
        return os.getenv("E2E_TESTING", "").lower() == "true"

    @classmethod
    def should_bypass_auth(cls) -> bool:
        """Check if auth should be bypassed.

        Auth is bypassed in:
        - Development mode (for local dev convenience)
        - E2E testing mode (browser tests need to skip real auth)

        NOT bypassed in:
        - Unit/integration tests (need to test auth behavior)
        - Production
        """
        return cls.is_development() or cls.is_e2e_testing()

    # Database
    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "chatbot.db")

    # File upload settings
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", str(20 * 1024 * 1024)))  # 20 MB default
    MAX_FILES_PER_MESSAGE: int = int(os.getenv("MAX_FILES_PER_MESSAGE", "10"))
    ALLOWED_FILE_TYPES: set[str] = set(
        os.getenv(
            "ALLOWED_FILE_TYPES",
            "image/png,image/jpeg,image/gif,image/webp,application/pdf,text/plain,text/markdown,application/json,text/csv",
        ).split(",")
    )

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of errors."""
        errors: list[str] = []

        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY is required")

        if not cls.is_development():
            if not cls.GOOGLE_CLIENT_ID:
                errors.append("GOOGLE_CLIENT_ID is required (or set FLASK_ENV=development)")
            if not cls.ALLOWED_EMAILS:
                errors.append("ALLOWED_EMAILS is required (or set FLASK_ENV=development)")
            if cls.JWT_SECRET_KEY == "dev-secret-change-me":
                errors.append("JWT_SECRET_KEY must be set to a secure value in production")

        return errors
