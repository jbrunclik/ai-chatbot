from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any

import jwt
from flask import Request, g, jsonify, request

from src.config import Config
from src.db.models import User, db
from src.utils.logging import get_logger

logger = get_logger(__name__)


def create_token(user: User) -> str:
    """Create a JWT token for a user."""
    logger.debug("Creating JWT token", extra={"user_id": user.id, "email": user.email})
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "exp": datetime.now(UTC) + timedelta(hours=Config.JWT_EXPIRATION_HOURS),
        "iat": datetime.now(UTC),
    }
    token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
    logger.debug("JWT token created", extra={"user_id": user.id})
    return token


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM]
        )
        logger.debug("JWT token decoded successfully", extra={"user_id": payload.get("sub")})
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("JWT token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT token", extra={"error": str(e)})
        return None


def get_token_from_request(req: Request) -> str | None:
    """Extract JWT token from Authorization header."""
    auth_header = req.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None


def get_current_user() -> User | None:
    """Get the current authenticated user from the request context."""
    return getattr(g, "current_user", None)


def require_auth[F: Callable[..., Any]](f: F) -> F:
    """Decorator to require authentication for a route."""

    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        # Skip auth in development mode and E2E testing (not unit/integration tests)
        if Config.should_bypass_auth():
            # Create a default local user
            local_user = db.get_or_create_user(
                email="local@localhost",
                name="Local User",
            )
            g.current_user = local_user
            logger.debug("Auth bypassed", extra={"mode": Config.FLASK_ENV})
            return f(*args, **kwargs)

        token = get_token_from_request(request)
        if not token:
            logger.warning("Missing authentication token", extra={"path": request.path})
            return jsonify({"error": "Missing authentication token"}), 401

        payload = decode_token(token)
        if not payload:
            logger.warning("Invalid or expired token", extra={"path": request.path})
            return jsonify({"error": "Invalid or expired token"}), 401

        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Invalid token payload - missing sub", extra={"path": request.path})
            return jsonify({"error": "Invalid token payload"}), 401

        user = db.get_user_by_id(user_id)
        if not user:
            logger.warning(
                "User not found for token", extra={"user_id": user_id, "path": request.path}
            )
            return jsonify({"error": "User not found"}), 401

        g.current_user = user
        logger.debug("Authentication successful", extra={"user_id": user_id, "path": request.path})
        return f(*args, **kwargs)

    return decorated  # type: ignore[return-value]
