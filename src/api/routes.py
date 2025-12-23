import base64
import json
import queue
import threading
from collections.abc import Generator
from typing import Any

from flask import Blueprint, Response, request

from src.agent.chat_agent import ChatAgent, extract_metadata_from_response, generate_title
from src.api.utils import (
    build_chat_response,
    build_stream_done_event,
    extract_metadata_fields,
)
from src.auth.google_auth import GoogleAuthError, is_email_allowed, verify_google_id_token
from src.auth.jwt_auth import create_token, get_current_user, require_auth
from src.config import Config
from src.db.models import db
from src.utils.files import validate_files
from src.utils.images import extract_generated_images_from_tool_results, process_image_files

api = Blueprint("api", __name__, url_prefix="/api")
auth = Blueprint("auth", __name__, url_prefix="/auth")


# ============================================================================
# Auth Routes
# ============================================================================


@auth.route("/google", methods=["POST"])
def google_auth() -> tuple[dict[str, Any], int]:
    """Authenticate with Google ID token from Sign In with Google."""
    if Config.is_development():
        return {"error": "Authentication disabled in local mode"}, 400

    data = request.get_json() or {}
    id_token = data.get("credential")

    if not id_token:
        return {"error": "Missing credential"}, 400

    try:
        user_info = verify_google_id_token(id_token)
    except GoogleAuthError as e:
        return {"error": str(e)}, 401

    email = user_info.get("email", "")
    if not is_email_allowed(email):
        return {"error": "Email not authorized"}, 403

    # Create or get user
    user = db.get_or_create_user(
        email=email,
        name=user_info.get("name", email),
        picture=user_info.get("picture"),
    )

    # Generate JWT token
    token = create_token(user)

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
    conversations = db.list_conversations(user.id)
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

    if model not in Config.MODELS:
        return {"error": f"Invalid model. Choose from: {list(Config.MODELS.keys())}"}, 400

    conv = db.create_conversation(user.id, model=model)
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
    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        return {"error": "Conversation not found"}, 404

    messages = db.get_messages(conv_id)

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

    if model and model not in Config.MODELS:
        return {"error": f"Invalid model. Choose from: {list(Config.MODELS.keys())}"}, 400

    if not db.update_conversation(conv_id, user.id, title=title, model=model):
        return {"error": "Conversation not found"}, 404

    return {"status": "updated"}, 200


@api.route("/conversations/<conv_id>", methods=["DELETE"])
@require_auth
def delete_conversation(conv_id: str) -> tuple[dict[str, str], int]:
    """Delete a conversation."""
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth

    if not db.delete_conversation(conv_id, user.id):
        return {"error": "Conversation not found"}, 404

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
    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        return {"error": "Conversation not found"}, 404

    data = request.get_json() or {}
    message_text = data.get("message", "").strip()
    files = data.get("files", [])
    force_tools = data.get("force_tools", [])

    if not message_text and not files:
        return {"error": "Message or files required"}, 400

    # Validate files if present
    if files:
        is_valid, error = validate_files(files)
        if not is_valid:
            return {"error": error}, 400
        # Generate thumbnails for images
        files = process_image_files(files)

    # Save user message with separate content and files
    db.add_message(conv_id, "user", message_text, files=files if files else None)

    # Get previous agent state
    previous_state = db.get_agent_state(conv_id)

    # Create agent and get response
    try:
        agent = ChatAgent(model_name=conv.model)
        raw_response, new_state, tool_results = agent.chat_with_state(
            message_text, files, previous_state, force_tools=force_tools
        )

        # Extract metadata from response
        clean_response, metadata = extract_metadata_from_response(raw_response)
        sources, generated_images_meta = extract_metadata_fields(metadata)

        # Extract generated image files from tool results
        # Note: tool_results are returned separately since they're not persisted in state
        gen_image_files = extract_generated_images_from_tool_results(tool_results)

        # Ensure we have at least some content or files to save
        # If response is empty but we have generated images, use a default message
        if not clean_response and gen_image_files:
            clean_response = "I've generated the image for you."

        # Save response and state (with clean content, files, and metadata)
        assistant_msg = db.add_message(
            conv_id,
            "assistant",
            clean_response,
            files=gen_image_files if gen_image_files else None,
            sources=sources if sources else None,
            generated_images=generated_images_meta if generated_images_meta else None,
        )
        db.save_agent_state(conv_id, new_state)
    except Exception as e:
        # Log the error and return a proper error response
        import traceback

        print(f"Error in chat_batch: {e}")
        print(traceback.format_exc())
        return {"error": f"Failed to generate response: {str(e)}"}, 500

    # Auto-generate title from first message if still default
    if conv.title == "New Conversation":
        new_title = generate_title(message_text, clean_response)
        db.update_conversation(conv_id, user.id, title=new_title)

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
    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        return {"error": "Conversation not found"}, 404

    data = request.get_json() or {}
    message_text = data.get("message", "").strip()
    files = data.get("files", [])
    force_tools = data.get("force_tools", [])

    if not message_text and not files:
        return {"error": "Message or files required"}, 400

    # Validate files if present
    if files:
        is_valid, error = validate_files(files)
        if not is_valid:
            return {"error": error}, 400
        # Generate thumbnails for images
        files = process_image_files(files)

    # Save user message with separate content and files
    db.add_message(conv_id, "user", message_text, files=files if files else None)

    # Get conversation history for context
    messages = db.get_messages(conv_id)
    history = [
        {"role": m.role, "content": m.content, "files": m.files} for m in messages[:-1]
    ]  # Exclude the just-added message

    def generate() -> Generator[str, None, None]:
        """Generator that streams tokens as SSE events with keepalive support.

        Uses a separate thread to stream LLM tokens into a queue, while the main
        generator loop sends keepalives when no tokens are available. This prevents
        proxy timeouts during the LLM's "thinking" phase before tokens start flowing.

        The stream_chat generator yields:
        - str: individual text tokens
        - tuple[str, dict, list]: final (clean_content, metadata, tool_results) after all tokens
        """
        agent = ChatAgent(model_name=conv.model)
        token_queue: queue.Queue[
            str | tuple[str, dict[str, Any], list[dict[str, Any]]] | None | Exception
        ] = queue.Queue()

        def stream_tokens() -> None:
            """Background thread that streams tokens into the queue."""
            try:
                for item in agent.stream_chat(
                    message_text, files, history, force_tools=force_tools
                ):
                    token_queue.put(item)
                token_queue.put(None)  # Signal completion
            except Exception as e:
                token_queue.put(e)  # Signal error

        # Start streaming in background thread
        stream_thread = threading.Thread(target=stream_tokens, daemon=True)
        stream_thread.start()

        # Variables to capture final content, metadata, and tool results
        clean_content = ""
        metadata: dict[str, Any] = {}
        tool_results: list[dict[str, Any]] = []

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
                        # Final tuple with (clean_content, metadata, tool_results)
                        clean_content, metadata, tool_results = item
                    else:
                        # Got a token string - yield to frontend
                        yield f"data: {json.dumps({'type': 'token', 'text': item})}\n\n"

                except queue.Empty:
                    # No token available, send keepalive comment
                    # SSE comments start with ":" and are ignored by clients
                    yield ": keepalive\n\n"

            # Extract metadata fields
            sources, generated_images_meta = extract_metadata_fields(metadata)

            # Extract generated image files from tool results captured during streaming
            gen_image_files = extract_generated_images_from_tool_results(tool_results)

            # Save complete response to DB
            assistant_msg = db.add_message(
                conv_id,
                "assistant",
                clean_content,
                files=gen_image_files if gen_image_files else None,
                sources=sources if sources else None,
                generated_images=generated_images_meta if generated_images_meta else None,
            )

            # Auto-generate title from first message if still default
            if conv.title == "New Conversation":
                new_title = generate_title(message_text, clean_content)
                db.update_conversation(conv_id, user.id, title=new_title)

            # Build done event
            done_data = build_stream_done_event(
                assistant_msg, gen_image_files, sources, generated_images_meta
            )

            yield f"data: {json.dumps(done_data)}\n\n"

        except Exception as e:
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

    # Get the message
    message = db.get_message_by_id(message_id)
    if not message:
        return {"error": "Message not found"}, 404

    # Verify user owns the conversation
    conv = db.get_conversation(message.conversation_id, user.id)
    if not conv:
        return {"error": "Not authorized"}, 403

    # Get the file
    if not message.files or file_index >= len(message.files):
        return {"error": "File not found"}, 404

    file = message.files[file_index]
    file_type = file.get("type", "application/octet-stream")

    # Check if it's an image
    if not file_type.startswith("image/"):
        return {"error": "File is not an image"}, 400

    # Prefer thumbnail, fall back to full image if thumbnail doesn't exist
    thumbnail_data = file.get("thumbnail")
    if thumbnail_data:
        try:
            binary_data = base64.b64decode(thumbnail_data)
            return Response(
                binary_data,
                mimetype=file_type,
                headers={
                    "Cache-Control": "private, max-age=31536000",  # Cache for 1 year
                },
            )
        except Exception:
            # Fall through to full image
            pass

    # Fall back to full image if no thumbnail
    file_data = file.get("data", "")
    if not file_data:
        return {"error": "Image data not found"}, 404

    try:
        binary_data = base64.b64decode(file_data)
        return Response(
            binary_data,
            mimetype=file_type,
            headers={
                "Cache-Control": "private, max-age=31536000",
            },
        )
    except Exception:
        return {"error": "Invalid image data"}, 500


@api.route("/messages/<message_id>/files/<int:file_index>", methods=["GET"])
@require_auth
def get_message_file(message_id: str, file_index: int) -> Response | tuple[dict[str, str], int]:
    """Get a full-size file from a message.

    Returns the file as binary data with appropriate content-type header.
    """
    user = get_current_user()
    assert user is not None  # Guaranteed by @require_auth

    # Get the message
    message = db.get_message_by_id(message_id)
    if not message:
        return {"error": "Message not found"}, 404

    # Verify user owns the conversation
    conv = db.get_conversation(message.conversation_id, user.id)
    if not conv:
        return {"error": "Not authorized"}, 403

    # Get the file
    if not message.files or file_index >= len(message.files):
        return {"error": "File not found"}, 404

    file = message.files[file_index]
    file_data = file.get("data", "")
    file_type = file.get("type", "application/octet-stream")

    # Decode base64 and return as binary
    try:
        binary_data = base64.b64decode(file_data)
        return Response(
            binary_data,
            mimetype=file_type,
            headers={
                "Cache-Control": "private, max-age=31536000",  # Cache for 1 year
            },
        )
    except Exception:
        return {"error": "Invalid file data"}, 500
