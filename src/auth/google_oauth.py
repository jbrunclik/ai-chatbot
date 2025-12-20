from typing import Any
from urllib.parse import urlencode

import requests

from src.config import Config

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"


class GoogleOAuthError(Exception):
    """Exception raised for Google OAuth errors."""

    pass


def get_authorization_url(redirect_uri: str, state: str | None = None) -> str:
    """Generate the Google OAuth authorization URL."""
    params = {
        "client_id": Config.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    if state:
        params["state"] = state

    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for access tokens."""
    data = {
        "client_id": Config.GOOGLE_CLIENT_ID,
        "client_secret": Config.GOOGLE_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }

    response = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=10)

    if response.status_code != 200:
        raise GoogleOAuthError(f"Failed to exchange code: {response.text}")

    return response.json()  # type: ignore[no-any-return]


def get_user_info(access_token: str) -> dict[str, Any]:
    """Get user info from Google using the access token."""
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(GOOGLE_USERINFO_URL, headers=headers, timeout=10)

    if response.status_code != 200:
        raise GoogleOAuthError(f"Failed to get user info: {response.text}")

    return response.json()  # type: ignore[no-any-return]


def is_email_allowed(email: str) -> bool:
    """Check if the email is in the allowed list."""
    return email.lower() in [e.lower() for e in Config.ALLOWED_EMAILS]
