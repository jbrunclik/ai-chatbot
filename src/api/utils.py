"""API response building utilities."""

from typing import Any


def extract_metadata_fields(
    metadata: dict[str, Any] | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Extract sources and generated_images from metadata dict.

    Args:
        metadata: Metadata dict from extract_metadata_from_response, or None

    Returns:
        Tuple of (sources list, generated_images list)
    """
    if not metadata:
        return [], []
    sources = metadata.get("sources", [])
    generated_images = metadata.get("generated_images", [])
    return sources, generated_images


def build_response_files(
    gen_image_files: list[dict[str, Any]], message_id: str
) -> list[dict[str, Any]]:
    """Build file metadata list for API response.

    Args:
        gen_image_files: List of generated image file dicts
        message_id: The message ID to associate files with

    Returns:
        List of file metadata dicts with name, type, messageId, fileIndex
    """
    response_files = []
    for idx, f in enumerate(gen_image_files):
        response_files.append(
            {
                "name": f.get("name", ""),
                "type": f.get("type", ""),
                "messageId": message_id,
                "fileIndex": idx,
            }
        )
    return response_files


def build_chat_response(
    assistant_msg: Any,
    content: str,
    gen_image_files: list[dict[str, Any]],
    sources: list[dict[str, str]],
    generated_images_meta: list[dict[str, str]],
) -> dict[str, Any]:
    """Build chat response dictionary for batch endpoint.

    Args:
        assistant_msg: Message object from database
        content: The message content text
        gen_image_files: List of generated image file dicts
        sources: List of source dicts
        generated_images_meta: List of generated image metadata dicts

    Returns:
        Response dictionary with id, role, content, created_at, and optional files/sources/generated_images
    """
    response_data: dict[str, Any] = {
        "id": assistant_msg.id,
        "role": "assistant",
        "content": content,
        "created_at": assistant_msg.created_at.isoformat(),
    }

    if gen_image_files:
        response_data["files"] = build_response_files(gen_image_files, assistant_msg.id)
    if sources:
        response_data["sources"] = sources
    if generated_images_meta:
        response_data["generated_images"] = generated_images_meta

    return response_data


def build_stream_done_event(
    assistant_msg: Any,
    gen_image_files: list[dict[str, Any]],
    sources: list[dict[str, str]],
    generated_images_meta: list[dict[str, str]],
) -> dict[str, Any]:
    """Build done event dictionary for streaming endpoint.

    Args:
        assistant_msg: Message object from database
        gen_image_files: List of generated image file dicts
        sources: List of source dicts
        generated_images_meta: List of generated image metadata dicts

    Returns:
        Done event dictionary with type, id, created_at, and optional files/sources/generated_images
    """
    done_data: dict[str, Any] = {
        "type": "done",
        "id": assistant_msg.id,
        "created_at": assistant_msg.created_at.isoformat(),
    }

    if gen_image_files:
        done_data["files"] = build_response_files(gen_image_files, assistant_msg.id)
    if sources:
        done_data["sources"] = sources
    if generated_images_meta:
        done_data["generated_images"] = generated_images_meta

    return done_data
