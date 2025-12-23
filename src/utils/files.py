"""File validation utilities."""

import base64
from typing import Any

from src.config import Config
from src.utils.logging import get_logger

logger = get_logger(__name__)


def validate_files(files: list[dict[str, Any]]) -> tuple[bool, str]:
    """Validate uploaded files against config limits.

    Args:
        files: List of file dictionaries with 'name', 'type', 'data' keys

    Returns:
        Tuple of (is_valid, error_message)
    """
    if len(files) > Config.MAX_FILES_PER_MESSAGE:
        logger.warning(
            "Too many files",
            extra={"file_count": len(files), "max_allowed": Config.MAX_FILES_PER_MESSAGE},
        )
        return False, f"Too many files. Maximum is {Config.MAX_FILES_PER_MESSAGE}"

    for file in files:
        file_name = file.get("name", "unknown")
        # Check file type
        file_type = file.get("type", "")
        if file_type not in Config.ALLOWED_FILE_TYPES:
            logger.warning(
                "File type not allowed", extra={"file_name": file_name, "file_type": file_type}
            )
            return False, f"File type '{file_type}' is not allowed"

        # Check file size (base64 is ~4/3 larger than binary)
        data = file.get("data", "")
        try:
            decoded_size = len(base64.b64decode(data))
            if decoded_size > Config.MAX_FILE_SIZE:
                max_mb = Config.MAX_FILE_SIZE / (1024 * 1024)
                logger.warning(
                    "File too large",
                    extra={
                        "file_name": file_name,
                        "size": decoded_size,
                        "max_size": Config.MAX_FILE_SIZE,
                    },
                )
                return False, f"File '{file_name}' exceeds {max_mb:.0f}MB limit"
        except Exception as e:
            logger.warning(
                "Invalid file data encoding", extra={"file_name": file_name, "error": str(e)}
            )
            return False, "Invalid file data encoding"

    logger.debug("File validation passed", extra={"file_count": len(files)})
    return True, ""
