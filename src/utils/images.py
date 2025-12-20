"""Image processing utilities for thumbnail generation."""

import base64
import io
from typing import Any

from PIL import Image

# Thumbnail dimensions
THUMBNAIL_MAX_SIZE = (400, 400)
THUMBNAIL_QUALITY = 85


def generate_thumbnail(
    image_data: str, mime_type: str, max_size: tuple[int, int] = THUMBNAIL_MAX_SIZE
) -> str | None:
    """Generate a thumbnail from base64-encoded image data.

    Args:
        image_data: Base64-encoded image data
        mime_type: MIME type of the image (e.g., 'image/jpeg')
        max_size: Maximum (width, height) for the thumbnail

    Returns:
        Base64-encoded thumbnail data, or None if generation fails
    """
    if not mime_type.startswith("image/"):
        return None

    try:
        # Decode base64 image
        image_bytes = base64.b64decode(image_data)
        img: Image.Image = Image.open(io.BytesIO(image_bytes))

        # Handle RGBA images (PNG with transparency)
        if img.mode in ("RGBA", "LA", "P"):
            # Convert to RGB with white background for JPEG output
            if mime_type == "image/jpeg":
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background

        # Generate thumbnail (maintains aspect ratio)
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save to bytes
        output = io.BytesIO()

        # Use original format or fallback to JPEG
        if mime_type == "image/png":
            img.save(output, format="PNG", optimize=True)
        elif mime_type == "image/gif":
            img.save(output, format="GIF")
        elif mime_type == "image/webp":
            img.save(output, format="WEBP", quality=THUMBNAIL_QUALITY)
        else:
            # Default to JPEG
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.save(output, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)

        # Return base64-encoded thumbnail
        output.seek(0)
        return base64.b64encode(output.read()).decode("utf-8")

    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return None


def process_image_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Process a list of files and add thumbnails to images.

    Args:
        files: List of file dictionaries with 'name', 'type', 'data' keys

    Returns:
        Same list with 'thumbnail' key added to image files
    """
    for file in files:
        if file.get("type", "").startswith("image/"):
            thumbnail = generate_thumbnail(file.get("data", ""), file.get("type", ""))
            if thumbnail:
                file["thumbnail"] = thumbnail

    return files
