import json
from collections.abc import Generator
from typing import Any

from flask import Blueprint, Response, request

from src.agent.chat_agent import ChatAgent, generate_title
from src.auth.google_auth import GoogleAuthError, is_email_allowed, verify_google_id_token
from src.auth.jwt_auth import create_token, get_current_user, require_auth
from src.config import Config
from src.db.models import db

api = Blueprint("api", __name__, url_prefix="/api")
auth = Blueprint("auth", __name__, url_prefix="/auth")


# ============================================================================
# Auth Routes
# ============================================================================


@auth.route("/google", methods=["POST"])
def google_auth() -> tuple[dict[str, Any], int]:
    """Authenticate with Google ID token from Sign In with Google."""
    if Config.LOCAL_MODE:
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
    if not user:
        return {"user": {}}

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
    if not user:
        return {"conversations": []}

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
    if not user:
        return {"error": "Unauthorized"}, 401

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
    """Get a conversation with its messages."""
    user = get_current_user()
    if not user:
        return {"error": "Unauthorized"}, 401

    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        return {"error": "Conversation not found"}, 404

    messages = db.get_messages(conv_id)
    return {
        "id": conv.id,
        "title": conv.title,
        "model": conv.model,
        "created_at": conv.created_at.isoformat(),
        "updated_at": conv.updated_at.isoformat(),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }, 200


@api.route("/conversations/<conv_id>", methods=["PATCH"])
@require_auth
def update_conversation(conv_id: str) -> tuple[dict[str, str], int]:
    """Update a conversation (title, model)."""
    user = get_current_user()
    if not user:
        return {"error": "Unauthorized"}, 401

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
    if not user:
        return {"error": "Unauthorized"}, 401

    if not db.delete_conversation(conv_id, user.id):
        return {"error": "Conversation not found"}, 404

    return {"status": "deleted"}, 200


# ============================================================================
# Chat Routes
# ============================================================================


@api.route("/conversations/<conv_id>/chat/batch", methods=["POST"])
@require_auth
def chat_batch(conv_id: str) -> tuple[dict[str, str], int]:
    """Send a message and get a complete response (non-streaming)."""
    user = get_current_user()
    if not user:
        return {"error": "Unauthorized"}, 401

    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        return {"error": "Conversation not found"}, 404

    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return {"error": "Message is required"}, 400

    # Save user message
    db.add_message(conv_id, "user", message)

    # Get previous agent state
    previous_state = db.get_agent_state(conv_id)

    # Create agent and get response
    agent = ChatAgent(model_name=conv.model)
    response, new_state = agent.chat_with_state(message, previous_state)

    # Save response and state
    assistant_msg = db.add_message(conv_id, "assistant", response)
    db.save_agent_state(conv_id, new_state)

    # Auto-generate title from first message if still default
    if conv.title == "New Conversation":
        new_title = generate_title(message, response)
        db.update_conversation(conv_id, user.id, title=new_title)

    return {
        "id": assistant_msg.id,
        "role": "assistant",
        "content": response,
        "created_at": assistant_msg.created_at.isoformat(),
    }, 200


@api.route("/conversations/<conv_id>/chat/stream", methods=["POST"])
@require_auth
def chat_stream(conv_id: str) -> Response | tuple[dict[str, str], int]:
    """Send a message and stream the response via Server-Sent Events."""
    user = get_current_user()
    if not user:
        return {"error": "Unauthorized"}, 401

    conv = db.get_conversation(conv_id, user.id)
    if not conv:
        return {"error": "Conversation not found"}, 404

    data = request.get_json() or {}
    message = data.get("message", "").strip()
    if not message:
        return {"error": "Message is required"}, 400

    # Save user message
    db.add_message(conv_id, "user", message)

    # Get conversation history for context
    messages = db.get_messages(conv_id)
    history = [
        {"role": m.role, "content": m.content} for m in messages[:-1]
    ]  # Exclude the just-added message

    def generate() -> Generator[str, None, None]:
        """Generator that streams tokens as SSE events."""
        agent = ChatAgent(model_name=conv.model)
        full_response = ""

        try:
            for token in agent.stream_chat(message, history):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

            # Save complete response to DB
            assistant_msg = db.add_message(conv_id, "assistant", full_response)

            # Auto-generate title from first message if still default
            if conv.title == "New Conversation":
                new_title = generate_title(message, full_response)
                db.update_conversation(conv_id, user.id, title=new_title)

            yield f"data: {json.dumps({'type': 'done', 'id': assistant_msg.id, 'created_at': assistant_msg.created_at.isoformat()})}\n\n"

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
