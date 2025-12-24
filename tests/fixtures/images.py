"""Image fixtures for testing."""

import base64
import io

from PIL import Image


def create_test_png(width: int = 100, height: int = 100, color: str = "red") -> str:
    """Create a test PNG image and return base64-encoded data.

    Args:
        width: Image width in pixels
        height: Image height in pixels
        color: Fill color name

    Returns:
        Base64-encoded PNG data
    """
    img = Image.new("RGB", (width, height), color=color)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def create_test_jpeg(width: int = 100, height: int = 100, color: str = "blue") -> str:
    """Create a test JPEG image and return base64-encoded data.

    Args:
        width: Image width in pixels
        height: Image height in pixels
        color: Fill color name

    Returns:
        Base64-encoded JPEG data
    """
    img = Image.new("RGB", (width, height), color=color)
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# Pre-generated minimal 1x1 red PNG (for tests that don't need Pillow)
MINIMAL_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIA"
    "C/wfxQAAAABJRU5ErkJggg=="
)
