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

    # Request timeouts (generous defaults to accommodate image generation and complex tool chains)
    # Image generation alone can take 30-60s, complex queries with multiple tools need more time
    CHAT_TIMEOUT: int = int(os.getenv("CHAT_TIMEOUT", "300"))  # 5 minutes for full chat request
    TOOL_TIMEOUT: int = int(os.getenv("TOOL_TIMEOUT", "90"))  # 90 seconds per tool execution
    GOOGLE_AUTH_TIMEOUT: int = int(
        os.getenv("GOOGLE_AUTH_TIMEOUT", "10")
    )  # 10 seconds for Google token verification

    # Streaming cleanup thread timeouts
    STREAM_CLEANUP_THREAD_TIMEOUT: int = int(
        os.getenv("STREAM_CLEANUP_THREAD_TIMEOUT", "600")
    )  # 10 minutes for stream thread to complete
    STREAM_CLEANUP_WAIT_DELAY: float = float(
        os.getenv("STREAM_CLEANUP_WAIT_DELAY", "1.0")
    )  # 1 second delay before checking if message was saved

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()

    # Slow query logging (only active in development/debug mode)
    SLOW_QUERY_THRESHOLD_MS: int = int(os.getenv("SLOW_QUERY_THRESHOLD_MS", "100"))

    # Cost tracking
    COST_CURRENCY: str = os.getenv("COST_CURRENCY", "CZK").upper()  # Default to CZK
    COST_HISTORY_MAX_MONTHS: int = int(
        os.getenv("COST_HISTORY_MAX_MONTHS", "120")
    )  # Max 10 years of history (120 months)

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

    # Image thumbnail settings
    THUMBNAIL_MAX_SIZE: tuple[int, int] = (
        int(os.getenv("THUMBNAIL_MAX_WIDTH", "400")),
        int(os.getenv("THUMBNAIL_MAX_HEIGHT", "400")),
    )
    THUMBNAIL_QUALITY: int = int(os.getenv("THUMBNAIL_QUALITY", "85"))  # JPEG quality (1-100)

    # Cost history settings
    COST_HISTORY_DEFAULT_LIMIT: int = int(
        os.getenv("COST_HISTORY_DEFAULT_LIMIT", "12")
    )  # Default to 12 months

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of errors with clear guidance."""
        errors: list[str] = []

        # Always required
        if not cls.GEMINI_API_KEY:
            errors.append(
                "GEMINI_API_KEY is required. "
                "Get your API key from https://ai.google.dev/ and set it in .env"
            )

        # Production-only requirements
        if not cls.is_development():
            if not cls.GOOGLE_CLIENT_ID:
                errors.append(
                    "GOOGLE_CLIENT_ID is required in production. "
                    "Set up OAuth at https://console.cloud.google.com/apis/credentials "
                    "or set FLASK_ENV=development to skip authentication"
                )
            if not cls.ALLOWED_EMAILS:
                errors.append(
                    "ALLOWED_EMAILS is required in production. "
                    "Set a comma-separated list of allowed email addresses "
                    "or set FLASK_ENV=development to skip authentication"
                )
            if cls.JWT_SECRET_KEY == "dev-secret-change-me":
                errors.append(
                    "JWT_SECRET_KEY must be set to a secure random value in production. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )
            elif len(cls.JWT_SECRET_KEY) < 32:
                errors.append(
                    f"JWT_SECRET_KEY must be at least 32 characters for security (got {len(cls.JWT_SECRET_KEY)}). "
                    'Generate a secure key with: python -c "import secrets; print(secrets.token_hex(32))"'
                )

        # Validate numeric ranges
        if cls.PORT < 1 or cls.PORT > 65535:
            errors.append(f"PORT must be between 1 and 65535, got {cls.PORT}")

        if cls.MAX_FILE_SIZE < 1:
            errors.append(f"MAX_FILE_SIZE must be positive, got {cls.MAX_FILE_SIZE}")

        if cls.MAX_FILES_PER_MESSAGE < 1:
            errors.append(
                f"MAX_FILES_PER_MESSAGE must be at least 1, got {cls.MAX_FILES_PER_MESSAGE}"
            )

        # Validate currency
        if cls.COST_CURRENCY not in cls.CURRENCY_RATES:
            valid_currencies = ", ".join(sorted(cls.CURRENCY_RATES.keys()))
            errors.append(
                f"COST_CURRENCY '{cls.COST_CURRENCY}' is not supported. "
                f"Valid currencies: {valid_currencies}"
            )

        # Validate log level
        valid_log_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if cls.LOG_LEVEL not in valid_log_levels:
            errors.append(
                f"LOG_LEVEL '{cls.LOG_LEVEL}' is not valid. "
                f"Valid levels: {', '.join(sorted(valid_log_levels))}"
            )

        return errors
