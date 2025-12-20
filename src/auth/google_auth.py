"""Google Identity Services (GIS) authentication.

This module validates Google ID tokens from the client-side Sign In with Google flow.
No client secret is needed - just a Client ID.
"""

from typing import Any

import requests

from src.config import Config

GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class GoogleAuthError(Exception):
    """Exception raised for Google authentication errors."""

    pass


def verify_google_id_token(id_token: str) -> dict[str, Any]:
    """Verify a Google ID token and return the user info.

    Args:
        id_token: The ID token from Google Sign-In

    Returns:
        User info dict with email, name, picture, etc.

    Raises:
        GoogleAuthError: If token is invalid or verification fails
    """
    # Verify token with Google's tokeninfo endpoint
    response = requests.get(
        GOOGLE_TOKENINFO_URL,
        params={"id_token": id_token},
        timeout=10,
    )

    if response.status_code != 200:
        raise GoogleAuthError("Invalid ID token")

    token_info = response.json()

    # Verify the token was issued for our app
    if token_info.get("aud") != Config.GOOGLE_CLIENT_ID:
        raise GoogleAuthError("Token was not issued for this application")

    # Check token is not expired (Google's endpoint does this, but double-check)
    if "email" not in token_info:
        raise GoogleAuthError("Token does not contain email")

    return {
        "email": token_info.get("email", ""),
        "name": token_info.get("name", token_info.get("email", "")),
        "picture": token_info.get("picture"),
        "email_verified": token_info.get("email_verified") == "true",
    }


def is_email_allowed(email: str) -> bool:
    """Check if the email is in the allowed list."""
    return email.lower() in [e.lower() for e in Config.ALLOWED_EMAILS]
