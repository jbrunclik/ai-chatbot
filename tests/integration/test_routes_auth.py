"""Integration tests for authentication routes."""

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

if TYPE_CHECKING:
    from src.db.models import User


class TestGoogleAuthRoute:
    """Tests for POST /auth/google endpoint."""

    def test_successful_login_new_user(
        self, client: FlaskClient, mock_google_tokeninfo: MagicMock
    ) -> None:
        """Should create user and return JWT on successful Google auth."""
        response = client.post(
            "/auth/google",
            json={"credential": "valid-google-token"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "test@example.com"

    def test_successful_login_existing_user(
        self,
        client: FlaskClient,
        mock_google_tokeninfo: MagicMock,
        test_user: "User",
    ) -> None:
        """Should return JWT for existing user."""
        response = client.post(
            "/auth/google",
            json={"credential": "valid-google-token"},
        )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["user"]["id"] == test_user.id

    def test_missing_token(self, client: FlaskClient) -> None:
        """Should return 400 when token is missing."""
        response = client.post("/auth/google", json={})

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_invalid_token(self, client: FlaskClient) -> None:
        """Should return 401 for invalid Google token."""
        with patch("src.auth.google_auth.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_get.return_value = mock_response

            response = client.post(
                "/auth/google",
                json={"credential": "invalid-token"},
            )

        assert response.status_code == 401
        data = json.loads(response.data)
        assert "error" in data

    def test_email_not_allowed(self, client: FlaskClient) -> None:
        """Should return 403 when email is not in allowed list."""
        with patch("src.auth.google_auth.requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "aud": "test-client-id",
                "email": "unauthorized@example.com",
                "name": "Unauthorized User",
                "email_verified": "true",
            }
            mock_get.return_value = mock_response

            response = client.post(
                "/auth/google",
                json={"credential": "valid-token"},
            )

        assert response.status_code == 403
        data = json.loads(response.data)
        # Error can be string or structured object
        error = data["error"]
        error_message = error["message"] if isinstance(error, dict) else error
        assert "not authorized" in error_message.lower()


class TestAuthMeRoute:
    """Tests for GET /auth/me endpoint."""

    def test_returns_current_user(
        self, client: FlaskClient, auth_headers: dict[str, str], test_user: "User"
    ) -> None:
        """Should return current authenticated user info."""
        response = client.get("/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["user"]["id"] == test_user.id
        assert data["user"]["email"] == test_user.email
        assert data["user"]["name"] == test_user.name

    def test_requires_auth(self, client: FlaskClient) -> None:
        """Should return 401 without auth token."""
        response = client.get("/auth/me")

        assert response.status_code == 401
        data = json.loads(response.data)
        assert "error" in data

    def test_invalid_token(self, client: FlaskClient) -> None:
        """Should return 401 for invalid token."""
        response = client.get(
            "/auth/me",
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert response.status_code == 401


class TestAuthClientIdRoute:
    """Tests for GET /auth/client-id endpoint."""

    def test_returns_client_id(self, client: FlaskClient) -> None:
        """Should return Google Client ID (no auth required)."""
        response = client.get("/auth/client-id")

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "client_id" in data
        assert data["client_id"] == "test-client-id"

    def test_no_auth_required(self, client: FlaskClient) -> None:
        """Should work without authentication."""
        # No auth headers
        response = client.get("/auth/client-id")
        assert response.status_code == 200
