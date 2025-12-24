import base64
import json
import queue
import threading
import uuid
from collections.abc import Generator
from datetime import datetime
from typing import Any

from flask import Blueprint, Response, request

from src.agent.chat_agent import (
    ChatAgent,
    extract_metadata_from_response,
    generate_title,
    get_full_tool_results,
    set_current_request_id,
)
from src.api.utils import (
    build_chat_response,
    build_stream_done_event,
    calculate_and_save_message_cost,
    extract_metadata_fields,
)
from src.auth.google_auth import GoogleAuthError, is_email_allowed, verify_google_id_token
from src.auth.jwt_auth import create_token, get_current_user, require_auth
from src.config import Config
from src.db.models import db
from src.utils.costs import convert_currency, format_cost
from src.utils.files import validate_files
from src.utils.images import extract_generated_images_from_tool_results, process_image_files
from src.utils.logging import get_logger, log_payload_snippet

logger = get_logger(__name__)

api = Blueprint("api", __name__, url_prefix="/api")
auth = Blueprint("auth", __name__, url_prefix="/auth")


# ============================================================================
# Auth Routes
# ============================================================================


@auth.route("/google", methods=["POST"])
def google_auth() -> tuple[dict[str, Any], int]:
    """Authenticate with Google ID token from Sign In with Google."""
    logger.info("Google authentication request")
    if Config.is_development():
        logger.warning("Authentication attempted in development mode")
        return {"error": "Authentication disabled in local mode"}, 400

    data = request.get_json() or {}
    id_token = data.get("credential")

    if not id_token:
        logger.warning("Google auth request missing credential")
        return {"error": "Missing credential"}, 400

    try:
        logger.debug("Verifying Google ID token")
        user_info = verify_google_id_token(id_token)
        email = user_info.get("email", "")
        logger.debug("Google token verified", extra={"email": email})
    except GoogleAuthError as e:
        logger.warning("Google token verification failed", extra={"error": str(e)})
        return {"error": str(e)}, 401

    if not is_email_allowed(email):
        logger.warning("Email not in whitelist", extra={"email": email})
        return {"error": "Email not authorized"}, 403

    # Create or get user
    logger.debug("Getting or creating user", extra={"email": email})
    user = db.get_or_create_user(
        email=email,
        name=user_info.get("name", email),
        picture=user_info.get("picture"),
    )

    # Generate JWT token
    token = create_token(user)
    logger.info("Google authentication successful", extra={"user_id": user.id, "email": email})

    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
        },
    }, 200


@auth.route("/client-id", methods=["GET"])
def get_client_id() -> dict[str, str]:
    """Return Google Client ID for frontend initialization."""
    return {"client_id": Config.GOOGLE_CLIENT_ID}


@auth.route("/me")
@require_auth
def me() -> dict[str, dict[str, str | None]]:
    """Get current user info."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.picture,
        }
    }


# ============================================================================
# Conversation Routes
# ============================================================================


@api.route("/conversations", methods=["GET"])
@require_auth
def list_conversations() -> dict[str, list[dict[str, str]]]:
    """List all conversations for the current user."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    logger.debug("Listing conversations", extra={"user_id": user.id})
    conversations = db.list_conversations(user.id)
    logger.info(
        "Conversations listed",
        extra={"user_id": user.id, "count": len(conversations)},
    )
    return {
        "conversations": [
            {
                "id": c.id,
                "title": c.title,
                "model": c.model,
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in conversations
        ]
    }


@api.route("/conversations", methods=["POST"])
@require_auth
def create_conversation() -> tuple[dict[str, str], int]:
    """Create a new conversation."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    data = request.get_json() or {}
    model = data.get("model", Config.DEFAULT_MODEL)
    log_payload_snippet(logger, data)

    if model not in Config.MODELS:
        logger.warning(
            "Invalid model requested",
            extra={
                "user_id": user.id,
                "model": model,
                "available_models": list(Config.MODELS.keys()),
            },
        )
        return {"error": f"Invalid model. Choose from: {list(Config.MODELS.keys())}"}, 400

    logger.debug("Creating conversation", extra={"user_id": user.id, "model": model})
    conv = db.create_conversation(user.id, model=model)
    logger.info(
        "Conversation created",
        extra={"user_id": user.id, "conversation_id": conv.id, "model": model},
    )
    return {
        "id": conv.id,
        "title": conv.title,
        "model": conv.model,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
    }, 201


@api.route("/conversations/<conv_id>", methods=["GET"])
@require_auth
def get_conversation(conv_id: str) -> tuple[dict[str, Any], int]:
    """Get a conversation with its messages.

    Optimized: Only includes file metadata, not thumbnails or full file data.
    Thumbnails are fetched on-demand via /api/messages/<message_id>/files/<file_index>/thumbnail.
    Full files can be fetched via /api/messages/<message_id>/files/<file_index>.
    """
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    logger.debug("Getting conversation", extra={"user_id": user.id, "conversation_id": conv_id})
    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        logger.warning(
            "Conversation not found",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        return {"error": "Conversation not found"}, 404

    messages = db.get_messages(conv_id)
    logger.info(
        "Conversation retrieved",
        extra={
            "user_id": user.id,
            "conversation_id": conv_id,
            "message_count": len(messages),
        },
    )

    # Optimize file data: only include metadata, not thumbnails or full file data
    # Thumbnails are fetched on-demand via /api/messages/<message_id>/files/<file_index>/thumbnail
    optimized_messages = []
    for m in messages:
        optimized_files = []
        if m.files:
            for idx, file in enumerate(m.files):
                optimized_file = {
                    "name": file.get("name", ""),
                    "type": file.get("type", ""),
                    "messageId": m.id,
                    "fileIndex": idx,
                }
                optimized_files.append(optimized_file)

        msg_data: dict[str, Any] = {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "files": optimized_files,
            "created_at": m.created_at.isoformat(),
        }
        if m.sources:
            msg_data["sources"] = m.sources
        if m.generated_images:
            msg_data["generated_images"] = m.generated_images

        optimized_messages.append(msg_data)

    return {
        "id": conv.id,
        "title": conv.title,
        "model": conv.model,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": optimized_messages,
    }, 200


@api.route("/conversations/<conv_id>", methods=["PATCH"])
@require_auth
def update_conversation(conv_id: str) -> tuple[dict[str, str], int]:
    """Update a conversation (title, model)."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    data = request.get_json() or {}
    title = data.get("title")
    model = data.get("model")
    log_payload_snippet(logger, data)

    if model and model not in Config.MODELS:
        logger.warning(
            "Invalid model in update request",
            extra={"user_id": user.id, "conversation_id": conv_id, "model": model},
        )
        return {"error": f"Invalid model. Choose from: {list(Config.MODELS.keys())}"}, 400

    logger.debug(
        "Updating conversation",
        extra={"user_id": user.id, "conversation_id": conv_id, "title": title, "model": model},
    )
    if not db.update_conversation(conv_id, user.id, title=title, model=model):
        logger.warning(
            "Conversation not found for update",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        return {"error": "Conversation not found"}, 404

    logger.info("Conversation updated", extra={"user_id": user.id, "conversation_id": conv_id})
    return {"status": "updated"}, 200


@api.route("/conversations/<conv_id>", methods=["DELETE"])
@require_auth
def delete_conversation(conv_id: str) -> tuple[dict[str, str], int]:
    """Delete a conversation."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth

    logger.debug("Deleting conversation", extra={"user_id": user.id, "conversation_id": conv_id})
    if not db.delete_conversation(conv_id, user.id):
        logger.warning(
            "Conversation not found for deletion",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        return {"error": "Conversation not found"}, 404

    logger.info("Conversation deleted", extra={"user_id": user.id, "conversation_id": conv_id})
    return {"status": "deleted"}, 200


# ============================================================================
# Chat Routes
# ============================================================================


@api.route("/conversations/<conv_id>/chat/batch", methods=["POST"])
@require_auth
def chat_batch(conv_id: str) -> tuple[dict[str, str], int]:
    """Send a message and get a complete response (non-streaming).

    Accepts JSON body with:
    - message: str (required) - the text message
    - files: list[dict] (optional) - array of {name, type, data} file objects
    - force_tools: list[str] (optional) - list of tool names to force (e.g. ["web_search"])
    """
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    logger.info("Batch chat request", extra={"user_id": user.id, "conversation_id": conv_id})
    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        logger.warning(
            "Conversation not found for chat",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        return {"error": "Conversation not found"}, 404

    data = request.get_json() or {}
    message_text = data.get("message", "").strip()
    files = data.get("files", [])
    force_tools = data.get("force_tools", [])
    log_payload_snippet(
        logger,
        {"message_length": len(message_text), "file_count": len(files), "force_tools": force_tools},
    )

    if not message_text and not files:
        logger.warning(
            "Chat request missing message and files",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        return {"error": "Message or files required"}, 400

    # Validate files if present
    if files:
        logger.debug(
            "Validating files",
            extra={"user_id": user.id, "conversation_id": conv_id, "file_count": len(files)},
        )
        is_valid, error = validate_files(files)
        if not is_valid:
            logger.warning(
                "File validation failed",
                extra={
                    "user_id": user.id,
                    "conversation_id": conv_id,
                    "error": error,
                    "file_count": len(files),
                },
            )
            return {"error": error}, 400
        # Generate thumbnails for images
        logger.debug(
            "Processing image files for thumbnails",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        files = process_image_files(files)

    # Save user message with separate content and files
    logger.debug(
        "Saving user message",
        extra={
            "user_id": user.id,
            "conversation_id": conv_id,
            "message_length": len(message_text),
            "file_count": len(files) if files else 0,
        },
    )
    db.add_message(conv_id, "user", message_text, files=files if files else None)

    # Get conversation history (excluding files from previous messages to save tokens)
    messages = db.get_messages(conv_id)
    history = [
        {"role": m.role, "content": m.content} for m in messages[:-1]
    ]  # Exclude the just-added message
    logger.debug(
        "Starting chat agent",
        extra={
            "user_id": user.id,
            "conversation_id": conv_id,
            "model": conv.model,
            "history_length": len(history),
            "force_tools": force_tools,
        },
    )

    # Create agent and get response
    try:
        # Generate a unique request ID for capturing full tool results
        request_id = str(uuid.uuid4())
        set_current_request_id(request_id)

        agent = ChatAgent(model_name=conv.model)
        raw_response, tool_results, usage_info = agent.chat_batch(
            message_text, files, history, force_tools=force_tools
        )

        # Get the FULL tool results (with _full_result) captured before stripping
        # This is needed for extracting generated images, as the tool_results from
        # chat_batch have already been stripped
        full_tool_results = get_full_tool_results(request_id)
        set_current_request_id(None)  # Clean up

        logger.debug(
            "Chat agent completed",
            extra={
                "user_id": user.id,
                "conversation_id": conv_id,
                "response_length": len(raw_response),
                "tool_results_count": len(tool_results),
                "full_tool_results_count": len(full_tool_results),
                "input_tokens": usage_info.get("input_tokens", 0),
                "output_tokens": usage_info.get("output_tokens", 0),
                "usage_info": str(usage_info),
            },
        )

        # Extract metadata from response
        clean_response, metadata = extract_metadata_from_response(raw_response)
        sources, generated_images_meta = extract_metadata_fields(metadata)
        logger.debug(
            "Extracted metadata",
            extra={
                "user_id": user.id,
                "conversation_id": conv_id,
                "sources_count": len(sources) if sources else 0,
                "generated_images_count": len(generated_images_meta)
                if generated_images_meta
                else 0,
            },
        )

        # Extract generated image files from FULL tool results (before stripping)
        # We need the full results because they contain the _full_result.image data
        gen_image_files = extract_generated_images_from_tool_results(full_tool_results)
        if gen_image_files:
            logger.info(
                "Generated images extracted",
                extra={
                    "user_id": user.id,
                    "conversation_id": conv_id,
                    "image_count": len(gen_image_files),
                },
            )

        # Ensure we have at least some content or files to save
        # If response is empty but we have generated images, use a default message
        if not clean_response and gen_image_files:
            clean_response = "I've generated the image for you."

        # Save assistant message (with clean content, files, and metadata)
        logger.debug(
            "Saving assistant message",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        assistant_msg = db.add_message(
            conv_id,
            "assistant",
            clean_response,
            files=gen_image_files if gen_image_files else None,
            sources=sources if sources else None,
            generated_images=generated_images_meta if generated_images_meta else None,
        )

        # Calculate and save cost (use full_tool_results for image generation cost)
        calculate_and_save_message_cost(
            assistant_msg.id,
            conv_id,
            user.id,
            conv.model,
            usage_info,
            full_tool_results,
            len(clean_response),
            mode="batch",
        )

        logger.info(
            "Batch chat completed",
            extra={
                "user_id": user.id,
                "conversation_id": conv_id,
                "message_id": assistant_msg.id,
                "response_length": len(clean_response),
            },
        )
    except Exception as e:
        # Log the error and return a proper error response
        import traceback

        logger.error(
            "Error in chat_batch",
            extra={
                "user_id": user.id,
                "conversation_id": conv_id,
                "error": str(e),
                "traceback": traceback.format_exc(),
            },
            exc_info=True,
        )
        return {"error": f"Failed to generate response: {str(e)}"}, 500

    # Auto-generate title from first message if still default
    if conv.title == "New Conversation":
        logger.debug(
            "Auto-generating conversation title",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        new_title = generate_title(message_text, clean_response)
        db.update_conversation(conv_id, user.id, title=new_title)
        logger.debug(
            "Conversation title generated",
            extra={"user_id": user.id, "conversation_id": conv_id, "title": new_title},
        )

    # Build response
    response_data = build_chat_response(
        assistant_msg, clean_response, gen_image_files, sources, generated_images_meta
    )

    return response_data, 200


@api.route("/conversations/<conv_id>/chat/stream", methods=["POST"])
@require_auth
def chat_stream(conv_id: str) -> Response | tuple[dict[str, str], int]:
    """Send a message and stream the response via Server-Sent Events.

    Accepts JSON body with:
    - message: str (required) - the text message
    - files: list[dict] (optional) - array of {name, type, data} file objects
    - force_tools: list[str] (optional) - list of tool names to force (e.g. ["web_search"])

    Uses SSE keepalive heartbeats to prevent proxy timeouts during long LLM thinking phases.
    Keepalives are sent as SSE comments (: keepalive) which clients ignore but proxies see as activity.
    """
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    logger.info("Stream chat request", extra={"user_id": user.id, "conversation_id": conv_id})
    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        logger.warning(
            "Conversation not found for stream chat",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        return {"error": "Conversation not found"}, 404

    data = request.get_json() or {}
    message_text = data.get("message", "").strip()
    files = data.get("files", [])
    force_tools = data.get("force_tools", [])
    log_payload_snippet(
        logger,
        {"message_length": len(message_text), "file_count": len(files), "force_tools": force_tools},
    )

    if not message_text and not files:
        logger.warning(
            "Stream chat request missing message and files",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        return {"error": "Message or files required"}, 400

    # Validate files if present
    if files:
        logger.debug(
            "Validating files for stream",
            extra={"user_id": user.id, "conversation_id": conv_id, "file_count": len(files)},
        )
        is_valid, error = validate_files(files)
        if not is_valid:
            logger.warning(
                "File validation failed in stream",
                extra={
                    "user_id": user.id,
                    "conversation_id": conv_id,
                    "error": error,
                    "file_count": len(files),
                },
            )
            return {"error": error}, 400
        # Generate thumbnails for images
        logger.debug(
            "Processing image files for thumbnails in stream",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        files = process_image_files(files)

    # Save user message with separate content and files
    logger.debug(
        "Saving user message for stream",
        extra={
            "user_id": user.id,
            "conversation_id": conv_id,
            "message_length": len(message_text),
            "file_count": len(files) if files else 0,
        },
    )
    db.add_message(conv_id, "user", message_text, files=files if files else None)

    # Get conversation history for context
    # NOTE: We exclude files from history to avoid re-sending large base64 data for every message.
    # Only the current message files are sent to the LLM. Historical images are not needed
    # since the LLM has seen them before and they're stored in the conversation context.
    messages = db.get_messages(conv_id)
    history = [
        {"role": m.role, "content": m.content} for m in messages[:-1]
    ]  # Exclude the just-added message, exclude files from history
    logger.debug(
        "Starting stream chat agent",
        extra={
            "user_id": user.id,
            "conversation_id": conv_id,
            "model": conv.model,
            "history_length": len(history),
            "force_tools": force_tools,
        },
    )

    # Generate a unique request ID for capturing full tool results
    stream_request_id = str(uuid.uuid4())

    def generate() -> Generator[str, None, None]:
        """Generator that streams tokens as SSE events with keepalive support.

        Uses a separate thread to stream LLM tokens into a queue, while the main
        generator loop sends keepalives when no tokens are available. This prevents
        proxy timeouts during the LLM's "thinking" phase before tokens start flowing.

        The stream_chat generator yields:
        - str: individual text tokens
        - tuple[str, dict, list]: final (clean_content, metadata, tool_results) after all tokens
        """
        # Set request ID for this streaming request to capture full tool results
        set_current_request_id(stream_request_id)

        agent = ChatAgent(model_name=conv.model)
        token_queue: queue.Queue[
            str
            | tuple[str, dict[str, Any], list[dict[str, Any]], dict[str, Any]]
            | None
            | Exception
        ] = queue.Queue()

        def stream_tokens() -> None:
            """Background thread that streams tokens into the queue."""
            # Copy context from parent thread so contextvars are accessible
            # This is necessary because Python threads don't inherit context by default
            set_current_request_id(stream_request_id)
            try:
                logger.debug(
                    "Stream thread started", extra={"user_id": user.id, "conversation_id": conv_id}
                )
                token_count = 0
                for item in agent.stream_chat(
                    message_text, files, history, force_tools=force_tools
                ):
                    if isinstance(item, str):
                        token_count += 1
                    token_queue.put(item)
                logger.debug(
                    "Stream thread completed",
                    extra={
                        "user_id": user.id,
                        "conversation_id": conv_id,
                        "token_count": token_count,
                    },
                )
                token_queue.put(None)  # Signal completion
            except Exception as e:
                logger.error(
                    "Stream thread error",
                    extra={"user_id": user.id, "conversation_id": conv_id, "error": str(e)},
                    exc_info=True,
                )
                token_queue.put(e)  # Signal error

        # Start streaming in background thread
        # Note: The thread sets its own request_id via set_current_request_id()
        stream_thread = threading.Thread(target=stream_tokens, daemon=True)
        stream_thread.start()

        # Variables to capture final content, metadata, tool results, and usage info
        clean_content = ""
        metadata: dict[str, Any] = {}
        tool_results: list[dict[str, Any]] = []
        usage_info: dict[str, Any] = {}

        try:
            while True:
                try:
                    # Wait for token with timeout for keepalive
                    item = token_queue.get(timeout=Config.SSE_KEEPALIVE_INTERVAL)

                    if item is None:
                        # Stream completed successfully
                        break
                    elif isinstance(item, Exception):
                        # Error occurred
                        yield f"data: {json.dumps({'type': 'error', 'message': str(item)})}\n\n"
                        return
                    elif isinstance(item, tuple):
                        # Final tuple with (clean_content, metadata, tool_results, usage_info)
                        clean_content, metadata, tool_results, usage_info = item
                    else:
                        # Got a token string - yield to frontend
                        yield f"data: {json.dumps({'type': 'token', 'text': item})}\n\n"

                except queue.Empty:
                    # No token available, send keepalive comment
                    # SSE comments start with ":" and are ignored by clients
                    yield ": keepalive\n\n"

            # Extract metadata fields
            sources, generated_images_meta = extract_metadata_fields(metadata)
            logger.debug(
                "Extracted metadata from stream",
                extra={
                    "user_id": user.id,
                    "conversation_id": conv_id,
                    "sources_count": len(sources) if sources else 0,
                    "generated_images_count": len(generated_images_meta)
                    if generated_images_meta
                    else 0,
                },
            )

            # Get the FULL tool results (with _full_result) captured before stripping
            # This is needed for extracting generated images
            full_tool_results = get_full_tool_results(stream_request_id)
            set_current_request_id(None)  # Clean up

            # Extract generated image files from FULL tool results (before stripping)
            gen_image_files = extract_generated_images_from_tool_results(full_tool_results)
            if gen_image_files:
                logger.info(
                    "Generated images extracted from stream",
                    extra={
                        "user_id": user.id,
                        "conversation_id": conv_id,
                        "image_count": len(gen_image_files),
                    },
                )

            # Save complete response to DB
            logger.debug(
                "Saving assistant message from stream",
                extra={"user_id": user.id, "conversation_id": conv_id},
            )
            assistant_msg = db.add_message(
                conv_id,
                "assistant",
                clean_content,
                files=gen_image_files if gen_image_files else None,
                sources=sources if sources else None,
                generated_images=generated_images_meta if generated_images_meta else None,
            )

            # Calculate and save cost for streaming (use full_tool_results for image cost)
            calculate_and_save_message_cost(
                assistant_msg.id,
                conv_id,
                user.id,
                conv.model,
                usage_info,
                full_tool_results,
                len(clean_content),
                mode="stream",
            )

            # Auto-generate title from first message if still default
            if conv.title == "New Conversation":
                logger.debug(
                    "Auto-generating conversation title from stream",
                    extra={"user_id": user.id, "conversation_id": conv_id},
                )
                new_title = generate_title(message_text, clean_content)
                db.update_conversation(conv_id, user.id, title=new_title)
                logger.debug(
                    "Conversation title generated from stream",
                    extra={"user_id": user.id, "conversation_id": conv_id, "title": new_title},
                )

            # Build done event
            done_data = build_stream_done_event(
                assistant_msg, gen_image_files, sources, generated_images_meta
            )

            logger.info(
                "Stream chat completed",
                extra={
                    "user_id": user.id,
                    "conversation_id": conv_id,
                    "message_id": assistant_msg.id,
                    "response_length": len(clean_content),
                },
            )

            yield f"data: {json.dumps(done_data)}\n\n"

        except Exception as e:
            logger.error(
                "Error in stream generator",
                extra={
                    "user_id": user.id,
                    "conversation_id": conv_id,
                    "error": str(e),
                },
                exc_info=True,
            )
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ============================================================================
# Models Routes
# ============================================================================


@api.route("/models", methods=["GET"])
@require_auth
def list_models() -> dict[str, Any]:
    """List available models."""
    return {
        "models": [
            {"id": model_id, "name": model_name} for model_id, model_name in Config.MODELS.items()
        ],
        "default": Config.DEFAULT_MODEL,
    }


# ============================================================================
# Config Routes
# ============================================================================


@api.route("/config/upload", methods=["GET"])
@require_auth
def get_upload_config() -> dict[str, Any]:
    """Get file upload configuration for frontend."""
    return {
        "maxFileSize": Config.MAX_FILE_SIZE,
        "maxFilesPerMessage": Config.MAX_FILES_PER_MESSAGE,
        "allowedFileTypes": list(Config.ALLOWED_FILE_TYPES),
    }


# ============================================================================
# Version Routes
# ============================================================================


@api.route("/version", methods=["GET"])
def get_version() -> dict[str, str | None]:
    """Get current app version (JS bundle hash).

    This endpoint does not require authentication so version can be
    checked even before login. Used by frontend to detect when a new
    version is deployed and prompt users to reload.
    """
    from flask import current_app

    return {"version": current_app.config.get("APP_VERSION")}


# ============================================================================
# Image Routes
# ============================================================================


@api.route("/messages/<message_id>/files/<int:file_index>/thumbnail", methods=["GET"])
@require_auth
def get_message_thumbnail(
    message_id: str, file_index: int
) -> Response | tuple[dict[str, str], int]:
    """Get a thumbnail for an image file from a message.

    Returns the thumbnail as binary data with appropriate content-type header.
    Falls back to full image if thumbnail doesn't exist.
    """
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    logger.debug(
        "Getting thumbnail",
        extra={"user_id": user.id, "message_id": message_id, "file_index": file_index},
    )

    # Get the message
    message = db.get_message_by_id(message_id)
    if not message:
        logger.warning("Message not found for thumbnail", extra={"message_id": message_id})
        return {"error": "Message not found"}, 404

    # Verify user owns the conversation
    conv = db.get_conversation(message.conversation_id, user.id)
    if not conv:
        logger.warning(
            "Unauthorized thumbnail access", extra={"user_id": user.id, "message_id": message_id}
        )
        return {"error": "Not authorized"}, 403

    # Get the file
    if not message.files or file_index >= len(message.files):
        logger.warning(
            "File not found for thumbnail",
            extra={"message_id": message_id, "file_index": file_index},
        )
        return {"error": "File not found"}, 404

    file = message.files[file_index]
    file_type = file.get("type", "application/octet-stream")

    # Check if it's an image
    if not file_type.startswith("image/"):
        logger.warning(
            "Non-image file requested as thumbnail",
            extra={
                "user_id": user.id,
                "message_id": message_id,
                "conversation_id": message.conversation_id,
                "file_type": file_type,
            },
        )
        return {"error": "File is not an image"}, 400

    # Prefer thumbnail, fall back to full image if thumbnail doesn't exist
    thumbnail_data = file.get("thumbnail")
    if thumbnail_data:
        try:
            binary_data = base64.b64decode(thumbnail_data)
            logger.debug(
                "Returning thumbnail",
                extra={
                    "user_id": user.id,
                    "message_id": message_id,
                    "conversation_id": message.conversation_id,
                    "file_index": file_index,
                    "size": len(binary_data),
                },
            )
            return Response(
                binary_data,
                mimetype=file_type,
                headers={
                    "Cache-Control": "private, max-age=31536000",  # Cache for 1 year
                },
            )
        except Exception as e:
            logger.warning(
                "Failed to decode thumbnail, falling back to full image",
                extra={
                    "user_id": user.id,
                    "message_id": message_id,
                    "conversation_id": message.conversation_id,
                    "error": str(e),
                },
            )
            # Fall through to full image
            pass

    # Fall back to full image if no thumbnail
    file_data = file.get("data", "")
    if not file_data:
        logger.warning(
            "No image data found for thumbnail",
            extra={
                "user_id": user.id,
                "message_id": message_id,
                "conversation_id": message.conversation_id,
                "file_index": file_index,
            },
        )
        return {"error": "Image data not found"}, 404

    try:
        binary_data = base64.b64decode(file_data)
        logger.debug(
            "Returning full image as thumbnail fallback",
            extra={
                "user_id": user.id,
                "message_id": message_id,
                "conversation_id": message.conversation_id,
                "file_index": file_index,
                "size": len(binary_data),
            },
        )
        return Response(
            binary_data,
            mimetype=file_type,
            headers={
                "Cache-Control": "private, max-age=31536000",
            },
        )
    except Exception as e:
        logger.error("Failed to decode image data", extra={"error": str(e)}, exc_info=True)
        return {"error": "Invalid image data"}, 500


@api.route("/messages/<message_id>/files/<int:file_index>", methods=["GET"])
@require_auth
def get_message_file(message_id: str, file_index: int) -> Response | tuple[dict[str, str], int]:
    """Get a full-size file from a message.

    Returns the file as binary data with appropriate content-type header.
    """
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    logger.debug(
        "Getting file",
        extra={"user_id": user.id, "message_id": message_id, "file_index": file_index},
    )

    # Get the message
    message = db.get_message_by_id(message_id)
    if not message:
        logger.warning(
            "Message not found for file", extra={"user_id": user.id, "message_id": message_id}
        )
        return {"error": "Message not found"}, 404

    # Verify user owns the conversation
    conv = db.get_conversation(message.conversation_id, user.id)
    if not conv:
        logger.warning(
            "Unauthorized file access",
            extra={
                "user_id": user.id,
                "message_id": message_id,
                "conversation_id": message.conversation_id,
            },
        )
        return {"error": "Not authorized"}, 403

    # Get the file
    if not message.files or file_index >= len(message.files):
        logger.warning(
            "File not found",
            extra={
                "user_id": user.id,
                "message_id": message_id,
                "conversation_id": message.conversation_id,
                "file_index": file_index,
            },
        )
        return {"error": "File not found"}, 404

    file = message.files[file_index]
    file_data = file.get("data", "")
    file_type = file.get("type", "application/octet-stream")

    # Decode base64 and return as binary
    try:
        binary_data = base64.b64decode(file_data)
        logger.debug(
            "Returning file",
            extra={
                "user_id": user.id,
                "message_id": message_id,
                "conversation_id": message.conversation_id,
                "file_index": file_index,
                "file_type": file_type,
                "size": len(binary_data),
            },
        )
        return Response(
            binary_data,
            mimetype=file_type,
            headers={
                "Cache-Control": "private, max-age=31536000",  # Cache for 1 year
            },
        )
    except Exception as e:
        logger.error("Failed to decode file data", extra={"error": str(e)}, exc_info=True)
        return {"error": "Invalid file data"}, 500


# ============================================================================
# Cost Tracking Routes
# ============================================================================


@api.route("/conversations/<conv_id>/cost", methods=["GET"])
@require_auth
def get_conversation_cost(conv_id: str) -> tuple[dict[str, Any], int]:
    """Get total cost for a conversation."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    logger.debug(
        "Getting conversation cost", extra={"user_id": user.id, "conversation_id": conv_id}
    )

    # Verify conversation belongs to user
    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        logger.warning(
            "Conversation not found for cost query",
            extra={"user_id": user.id, "conversation_id": conv_id},
        )
        return {"error": "Conversation not found"}, 404

    cost_usd = db.get_conversation_cost(conv_id)
    cost_display = convert_currency(cost_usd, Config.COST_CURRENCY)
    formatted_cost = format_cost(cost_display, Config.COST_CURRENCY)

    logger.info(
        "Conversation cost retrieved",
        extra={"user_id": user.id, "conversation_id": conv_id, "cost_usd": cost_usd},
    )

    return {
        "conversation_id": conv_id,
        "cost_usd": cost_usd,
        "cost": cost_display,
        "currency": Config.COST_CURRENCY,
        "formatted": formatted_cost,
    }, 200


@api.route("/messages/<message_id>/cost", methods=["GET"])
@require_auth
def get_message_cost(message_id: str) -> tuple[dict[str, Any], int]:
    """Get cost for a specific message."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth
    logger.debug("Getting message cost", extra={"user_id": user.id, "message_id": message_id})

    # Verify message belongs to user
    message = db.get_message_by_id(message_id)
    if not message:
        logger.warning(
            "Message not found for cost query",
            extra={"user_id": user.id, "message_id": message_id},
        )
        return {"error": "Message not found"}, 404

    conv = db.get_conversation(message.conversation_id, user.id)
    if not conv:
        logger.warning(
            "Conversation not found for message cost query",
            extra={
                "user_id": user.id,
                "message_id": message_id,
                "conversation_id": message.conversation_id,
            },
        )
        return {"error": "Message not found"}, 404

    cost_data = db.get_message_cost(message_id)
    if not cost_data:
        logger.debug(
            "No cost data found for message",
            extra={"user_id": user.id, "message_id": message_id},
        )
        return {"error": "No cost data available for this message"}, 404

    cost_display = convert_currency(cost_data["cost_usd"], Config.COST_CURRENCY)
    formatted_cost = format_cost(cost_display, Config.COST_CURRENCY)

    image_gen_cost_usd = cost_data.get("image_generation_cost_usd", 0.0)
    image_gen_cost_display = convert_currency(image_gen_cost_usd, Config.COST_CURRENCY)
    image_gen_cost_formatted = (
        format_cost(image_gen_cost_display, Config.COST_CURRENCY)
        if image_gen_cost_usd > 0
        else None
    )

    logger.info(
        "Message cost retrieved",
        extra={
            "user_id": user.id,
            "message_id": message_id,
            "cost_usd": cost_data["cost_usd"],
            "image_generation_cost_usd": image_gen_cost_usd,
        },
    )

    response = {
        "message_id": message_id,
        "cost_usd": cost_data["cost_usd"],
        "cost": cost_display,
        "currency": Config.COST_CURRENCY,
        "formatted": formatted_cost,
        "input_tokens": cost_data["input_tokens"],
        "output_tokens": cost_data["output_tokens"],
        "model": cost_data["model"],
    }

    if image_gen_cost_usd > 0:
        response["image_generation_cost_usd"] = image_gen_cost_usd
        response["image_generation_cost"] = image_gen_cost_display
        response["image_generation_cost_formatted"] = image_gen_cost_formatted

    return response, 200


@api.route("/users/me/costs/monthly", methods=["GET"])
@require_auth
def get_user_monthly_cost() -> tuple[dict[str, Any], int]:
    """Get cost for the current user in a specific month."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth

    # Get year and month from query params (default to current month)
    now = datetime.now()
    year = request.args.get("year", type=int) or now.year
    month = request.args.get("month", type=int) or now.month

    # Validate month range
    if not (1 <= month <= 12):
        logger.warning(
            "Invalid month in request",
            extra={"user_id": user.id, "year": year, "month": month},
        )
        return {"error": "Month must be between 1 and 12"}, 400

    logger.debug(
        "Getting user monthly cost",
        extra={"user_id": user.id, "year": year, "month": month},
    )

    cost_data = db.get_user_monthly_cost(user.id, year, month)
    cost_display = convert_currency(cost_data["total_usd"], Config.COST_CURRENCY)
    formatted_cost = format_cost(cost_display, Config.COST_CURRENCY)

    # Convert breakdown to display currency
    breakdown_display = {}
    for model, data in cost_data["breakdown"].items():
        breakdown_display[model] = {
            "total": convert_currency(data["total_usd"], Config.COST_CURRENCY),
            "total_usd": data["total_usd"],
            "message_count": data["message_count"],
            "formatted": format_cost(
                convert_currency(data["total_usd"], Config.COST_CURRENCY), Config.COST_CURRENCY
            ),
        }

    logger.info(
        "User monthly cost retrieved",
        extra={
            "user_id": user.id,
            "year": year,
            "month": month,
            "total_usd": cost_data["total_usd"],
            "message_count": cost_data["message_count"],
        },
    )

    return {
        "user_id": user.id,
        "year": year,
        "month": month,
        "total_usd": cost_data["total_usd"],
        "total": cost_display,
        "currency": Config.COST_CURRENCY,
        "formatted": formatted_cost,
        "message_count": cost_data["message_count"],
        "breakdown": breakdown_display,
    }, 200


@api.route("/users/me/costs/history", methods=["GET"])
@require_auth
def get_user_cost_history() -> tuple[dict[str, Any], int]:
    """Get monthly cost history for the current user."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth

    limit = request.args.get("limit", type=int) or 12
    # Cap limit to prevent performance issues (max 10 years of history)
    limit = min(limit, 120)
    logger.debug("Getting user cost history", extra={"user_id": user.id, "limit": limit})

    history = db.get_user_cost_history(user.id, limit)

    # Get current month
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # Convert each month's cost to display currency
    history_display = []
    current_month_in_history = False
    for month_data in history:
        year = month_data["year"]
        month = month_data["month"]

        # Check if this is the current month
        if year == current_year and month == current_month:
            current_month_in_history = True

        cost_display = convert_currency(month_data["total_usd"], Config.COST_CURRENCY)
        history_display.append(
            {
                "year": year,
                "month": month,
                "total_usd": month_data["total_usd"],
                "total": cost_display,
                "currency": Config.COST_CURRENCY,
                "formatted": format_cost(cost_display, Config.COST_CURRENCY),
                "message_count": month_data["message_count"],
            }
        )

    # If current month is not in history, add it with $0 cost
    if not current_month_in_history:
        history_display.insert(
            0,
            {
                "year": current_year,
                "month": current_month,
                "total_usd": 0.0,
                "total": 0.0,
                "currency": Config.COST_CURRENCY,
                "formatted": format_cost(0.0, Config.COST_CURRENCY),
                "message_count": 0,
            },
        )

    logger.info(
        "User cost history retrieved",
        extra={"user_id": user.id, "months_count": len(history_display)},
    )

    return {
        "user_id": user.id,
        "history": history_display,
    }, 200
