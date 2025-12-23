"""API response building utilities."""

import json
from typing import Any

from src.db.models import db
from src.utils.costs import calculate_total_cost
from src.utils.logging import get_logger

logger = get_logger(__name__)


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


def calculate_and_save_message_cost(
    message_id: str,
    conversation_id: str,
    user_id: str,
    model: str,
    usage_info: dict[str, Any],
    tool_results: list[dict[str, Any]],
    response_length: int,
    mode: str = "batch",
) -> None:
    """Calculate and save cost for a message.

    Args:
        message_id: The message ID
        conversation_id: The conversation ID
        user_id: The user ID
        model: The model used
        usage_info: Dict with 'input_tokens' and 'output_tokens'
        tool_results: List of tool result dicts
        response_length: Length of the response content (used for logging warnings when token metadata is missing)
        mode: 'batch' or 'stream' (for logging)
    """
    input_tokens = usage_info.get("input_tokens", 0)
    output_tokens = usage_info.get("output_tokens", 0)

    # Calculate image generation cost from tool_results
    image_cost = calculate_image_generation_cost_from_tool_results(tool_results)

    # Log warning if no usage metadata (should be rare - indicates API issue)
    if input_tokens == 0 and output_tokens == 0:
        logger.warning(
            f"No token usage metadata found in {mode} mode",
            extra={
                "user_id": user_id,
                "conversation_id": conversation_id,
                "model": model,
                "response_length": response_length,
            },
        )

    cost_usd = calculate_total_cost(
        model,
        input_tokens,
        output_tokens,
        image_generation_cost=image_cost,
    )

    db.save_message_cost(
        message_id,
        conversation_id,
        user_id,
        model,
        input_tokens,
        output_tokens,
        cost_usd,
        image_generation_cost_usd=image_cost,
    )

    logger.info(
        f"{mode.capitalize()} chat cost saved",
        extra={
            "user_id": user_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "cost_usd": cost_usd,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )


def calculate_image_generation_cost_from_tool_results(
    tool_results: list[dict[str, Any]],
) -> float:
    """Calculate total cost for all image generations from tool_results.

    Args:
        tool_results: List of tool result dicts with 'type' and 'content' keys

    Returns:
        Total cost in USD for all image generations (0.0 if no images or missing usage_metadata)
    """
    from src.utils.costs import calculate_image_generation_cost

    total_cost = 0.0

    for tool_result in tool_results:
        if not isinstance(tool_result, dict) or tool_result.get("type") != "tool":
            continue

        content = tool_result.get("content", "")
        if not content:
            continue

        try:
            content_data = json.loads(content) if isinstance(content, str) else {}
        except (json.JSONDecodeError, TypeError):
            continue

        # Check if this is a generate_image result with usage_metadata
        if isinstance(content_data, dict) and "image" in content_data:
            usage_metadata = content_data.get("usage_metadata")
            if usage_metadata:
                total_cost += calculate_image_generation_cost(usage_metadata)
            else:
                logger.warning(
                    "Image generation tool result missing usage_metadata",
                    extra={"tool_result_keys": list(content_data.keys())},
                )

    return total_cost
