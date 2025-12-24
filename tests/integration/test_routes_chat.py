"""Integration tests for chat routes."""

import json
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from flask.testing import FlaskClient

if TYPE_CHECKING:
    from src.db.models import Conversation, Database


class TestChatBatch:
    """Tests for POST /api/conversations/<conv_id>/chat/batch endpoint."""

    def test_successful_chat(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
    ) -> None:
        """Should return assistant response."""
        with patch("src.api.routes.ChatAgent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.chat_with_state.return_value = (
                "Hello! How can I help?",  # response
                {"messages": []},  # new_state
                [],  # tool_results
                {"input_tokens": 100, "output_tokens": 50},  # usage_info
            )
            mock_agent_class.return_value = mock_agent

            response = client.post(
                f"/api/conversations/{test_conversation.id}/chat/batch",
                headers=auth_headers,
                json={"message": "Hello!"},
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["role"] == "assistant"
        assert "Hello" in data["content"]

    def test_requires_message_or_files(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
    ) -> None:
        """Should return 400 when neither message nor files provided."""
        response = client.post(
            f"/api/conversations/{test_conversation.id}/chat/batch",
            headers=auth_headers,
            json={},
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_saves_messages_to_database(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
        test_database: "Database",
    ) -> None:
        """Should save user and assistant messages."""
        with patch("src.api.routes.ChatAgent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.chat_with_state.return_value = (
                "Response text",
                {"messages": []},
                [],
                {"input_tokens": 100, "output_tokens": 50},
            )
            mock_agent_class.return_value = mock_agent

            client.post(
                f"/api/conversations/{test_conversation.id}/chat/batch",
                headers=auth_headers,
                json={"message": "User message"},
            )

        messages = test_database.get_messages(test_conversation.id)
        assert len(messages) == 2
        assert messages[0].role == "user"
        assert messages[0].content == "User message"
        assert messages[1].role == "assistant"

    def test_includes_sources_in_response(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
    ) -> None:
        """Should include sources when web tools are used."""
        with patch("src.api.routes.ChatAgent") as mock_agent_class:
            mock_agent = MagicMock()
            # Response with metadata that will be extracted
            response_with_metadata = """Based on search results...

<!-- METADATA:
{"sources": [{"title": "Test Source", "url": "https://example.com"}]}
-->"""
            mock_agent.chat_with_state.return_value = (
                response_with_metadata,
                {"messages": []},
                [],
                {"input_tokens": 150, "output_tokens": 100},
            )
            mock_agent_class.return_value = mock_agent

            response = client.post(
                f"/api/conversations/{test_conversation.id}/chat/batch",
                headers=auth_headers,
                json={"message": "Search for something"},
            )

        assert response.status_code == 200
        data = json.loads(response.data)
        assert "sources" in data
        assert len(data["sources"]) == 1

    def test_returns_404_for_nonexistent_conversation(
        self, client: FlaskClient, auth_headers: dict[str, str]
    ) -> None:
        """Should return 404 for non-existent conversation."""
        response = client.post(
            "/api/conversations/nonexistent-id/chat/batch",
            headers=auth_headers,
            json={"message": "Hello"},
        )

        assert response.status_code == 404

    def test_requires_auth(
        self, client: FlaskClient, test_conversation: "Conversation"
    ) -> None:
        """Should return 401 without authentication."""
        response = client.post(
            f"/api/conversations/{test_conversation.id}/chat/batch",
            json={"message": "Hello"},
        )
        assert response.status_code == 401

    def test_force_tools_parameter(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
    ) -> None:
        """Should pass force_tools to agent."""
        with patch("src.api.routes.ChatAgent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.chat_with_state.return_value = (
                "Response",
                {"messages": []},
                [],
                {"input_tokens": 100, "output_tokens": 50},
            )
            mock_agent_class.return_value = mock_agent

            client.post(
                f"/api/conversations/{test_conversation.id}/chat/batch",
                headers=auth_headers,
                json={"message": "Hello", "force_tools": ["web_search"]},
            )

            # Verify force_tools was passed
            call_kwargs = mock_agent.chat_with_state.call_args.kwargs
            assert call_kwargs.get("force_tools") == ["web_search"]


class TestChatStream:
    """Tests for POST /api/conversations/<conv_id>/chat/stream endpoint."""

    def test_returns_sse_stream(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
    ) -> None:
        """Should return SSE content type."""
        with patch("src.api.routes.ChatAgent") as mock_agent_class:
            mock_agent = MagicMock()

            def mock_stream(*args: Any, **kwargs: Any) -> Any:
                yield "Hello"
                yield " world"
                yield (
                    "Hello world",
                    {},
                    [],
                    {"input_tokens": 50, "output_tokens": 10},
                )

            mock_agent.stream_chat = mock_stream
            mock_agent_class.return_value = mock_agent

            response = client.post(
                f"/api/conversations/{test_conversation.id}/chat/stream",
                headers=auth_headers,
                json={"message": "Hello"},
            )

        assert response.status_code == 200
        assert "text/event-stream" in response.content_type

    def test_streams_tokens(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
    ) -> None:
        """Should stream tokens as SSE events."""
        with patch("src.api.routes.ChatAgent") as mock_agent_class:
            mock_agent = MagicMock()

            def mock_stream(*args: Any, **kwargs: Any) -> Any:
                yield "Token1"
                yield "Token2"
                yield (
                    "Token1Token2",
                    {},
                    [],
                    {"input_tokens": 50, "output_tokens": 10},
                )

            mock_agent.stream_chat = mock_stream
            mock_agent_class.return_value = mock_agent

            response = client.post(
                f"/api/conversations/{test_conversation.id}/chat/stream",
                headers=auth_headers,
                json={"message": "Hello"},
            )

        # Check response contains SSE data events
        response_text = response.data.decode("utf-8")
        assert "data:" in response_text
        assert "Token1" in response_text or "Token2" in response_text

    def test_requires_message_or_files(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
    ) -> None:
        """Should return 400 when neither message nor files provided."""
        response = client.post(
            f"/api/conversations/{test_conversation.id}/chat/stream",
            headers=auth_headers,
            json={},
        )

        assert response.status_code == 400

    def test_returns_404_for_nonexistent_conversation(
        self, client: FlaskClient, auth_headers: dict[str, str]
    ) -> None:
        """Should return 404 for non-existent conversation."""
        response = client.post(
            "/api/conversations/nonexistent-id/chat/stream",
            headers=auth_headers,
            json={"message": "Hello"},
        )

        assert response.status_code == 404

    def test_requires_auth(
        self, client: FlaskClient, test_conversation: "Conversation"
    ) -> None:
        """Should return 401 without authentication."""
        response = client.post(
            f"/api/conversations/{test_conversation.id}/chat/stream",
            json={"message": "Hello"},
        )
        assert response.status_code == 401


class TestChatWithFiles:
    """Tests for chat endpoints with file attachments."""

    def test_batch_chat_with_files(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
        sample_file: dict[str, Any],
    ) -> None:
        """Should handle file attachments in batch mode."""
        with patch("src.api.routes.ChatAgent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.chat_with_state.return_value = (
                "I see your image",
                {"messages": []},
                [],
                {"input_tokens": 200, "output_tokens": 50},
            )
            mock_agent_class.return_value = mock_agent

            response = client.post(
                f"/api/conversations/{test_conversation.id}/chat/batch",
                headers=auth_headers,
                json={
                    "message": "What's in this image?",
                    "files": [sample_file],
                },
            )

        assert response.status_code == 200

    def test_files_only_no_message(
        self,
        client: FlaskClient,
        auth_headers: dict[str, str],
        test_conversation: "Conversation",
        sample_file: dict[str, Any],
    ) -> None:
        """Should accept files without text message."""
        with patch("src.api.routes.ChatAgent") as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent.chat_with_state.return_value = (
                "This is an image of...",
                {"messages": []},
                [],
                {"input_tokens": 200, "output_tokens": 50},
            )
            mock_agent_class.return_value = mock_agent

            response = client.post(
                f"/api/conversations/{test_conversation.id}/chat/batch",
                headers=auth_headers,
                json={
                    "message": "",
                    "files": [sample_file],
                },
            )

        assert response.status_code == 200
