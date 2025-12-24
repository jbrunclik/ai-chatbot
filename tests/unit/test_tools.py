"""Unit tests for src/agent/tools.py."""

import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.agent.tools import (
    VALID_ASPECT_RATIOS,
    fetch_url,
    generate_image,
    web_search,
)


class TestFetchUrl:
    """Tests for fetch_url tool."""

    @patch("src.agent.tools.httpx.Client")
    def test_fetches_html_content(self, mock_client_class: MagicMock) -> None:
        """Should fetch and extract text from HTML pages."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Hello World</p></body></html>"
        mock_response.headers = {"content-type": "text/html"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = fetch_url.invoke({"url": "https://example.com"})

        assert "Hello World" in result
        mock_client.get.assert_called_once_with("https://example.com")

    def test_rejects_invalid_url_scheme(self) -> None:
        """Should reject URLs without http/https scheme."""
        result = fetch_url.invoke({"url": "not-a-url"})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Invalid URL" in parsed["error"]

    def test_rejects_ftp_url(self) -> None:
        """Should reject non-HTTP URLs."""
        result = fetch_url.invoke({"url": "ftp://example.com/file.txt"})
        parsed = json.loads(result)
        assert "error" in parsed

    @patch("src.agent.tools.httpx.Client")
    def test_handles_timeout(self, mock_client_class: MagicMock) -> None:
        """Should return error on timeout."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.TimeoutException("Timeout")
        mock_client_class.return_value = mock_client

        result = fetch_url.invoke({"url": "https://slow.example.com"})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "timed out" in parsed["error"]

    @patch("src.agent.tools.httpx.Client")
    def test_handles_http_error(self, mock_client_class: MagicMock) -> None:
        """Should return error for HTTP errors."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )
        mock_client_class.return_value = mock_client

        result = fetch_url.invoke({"url": "https://example.com/404"})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "404" in parsed["error"]

    @patch("src.agent.tools.httpx.Client")
    def test_rejects_non_text_content(self, mock_client_class: MagicMock) -> None:
        """Should return error for non-text content types."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/pdf"}
        mock_response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = fetch_url.invoke({"url": "https://example.com/file.pdf"})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "non-text" in parsed["error"]


class TestWebSearch:
    """Tests for web_search tool."""

    @patch("src.agent.tools.DDGS")
    def test_returns_search_results(self, mock_ddgs_class: MagicMock) -> None:
        """Should return formatted search results."""
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = [
            {"title": "Result 1", "href": "https://example.com/1", "body": "Snippet 1"},
            {"title": "Result 2", "href": "https://example.com/2", "body": "Snippet 2"},
        ]
        mock_ddgs_class.return_value = mock_ddgs

        result = web_search.invoke({"query": "test query"})
        parsed = json.loads(result)

        assert parsed["query"] == "test query"
        assert len(parsed["results"]) == 2
        assert parsed["results"][0]["title"] == "Result 1"
        assert parsed["results"][0]["url"] == "https://example.com/1"
        assert parsed["results"][0]["snippet"] == "Snippet 1"

    @patch("src.agent.tools.DDGS")
    def test_handles_empty_results(self, mock_ddgs_class: MagicMock) -> None:
        """Should handle no search results."""
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = []
        mock_ddgs_class.return_value = mock_ddgs

        result = web_search.invoke({"query": "obscure query xyz123"})
        parsed = json.loads(result)

        assert parsed["results"] == []
        assert "error" in parsed  # Should include error message

    @patch("src.agent.tools.DDGS")
    def test_respects_num_results_limit(self, mock_ddgs_class: MagicMock) -> None:
        """Should pass num_results to DDGS."""
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = []
        mock_ddgs_class.return_value = mock_ddgs

        web_search.invoke({"query": "test", "num_results": 3})

        mock_ddgs.text.assert_called_once_with("test", max_results=3)

    @patch("src.agent.tools.DDGS")
    def test_caps_num_results_at_10(self, mock_ddgs_class: MagicMock) -> None:
        """Should cap num_results at 10."""
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.return_value = []
        mock_ddgs_class.return_value = mock_ddgs

        web_search.invoke({"query": "test", "num_results": 100})

        mock_ddgs.text.assert_called_once_with("test", max_results=10)

    @patch("src.agent.tools.DDGS")
    def test_handles_search_exception(self, mock_ddgs_class: MagicMock) -> None:
        """Should handle exceptions gracefully."""
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.text.side_effect = Exception("Search failed")
        mock_ddgs_class.return_value = mock_ddgs

        result = web_search.invoke({"query": "test"})
        parsed = json.loads(result)

        assert "error" in parsed
        assert parsed["results"] == []


class TestGenerateImage:
    """Tests for generate_image tool."""

    def test_rejects_empty_prompt(self) -> None:
        """Should reject empty prompts."""
        result = generate_image.invoke({"prompt": ""})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "empty" in parsed["error"].lower()

    def test_rejects_whitespace_only_prompt(self) -> None:
        """Should reject whitespace-only prompts."""
        result = generate_image.invoke({"prompt": "   "})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "empty" in parsed["error"].lower()

    def test_rejects_invalid_aspect_ratio(self) -> None:
        """Should reject invalid aspect ratios."""
        result = generate_image.invoke({"prompt": "test image", "aspect_ratio": "5:3"})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Invalid aspect ratio" in parsed["error"]

    def test_valid_aspect_ratios_constant(self) -> None:
        """Verify valid aspect ratios are defined."""
        expected_ratios = {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"}
        assert VALID_ASPECT_RATIOS == expected_ratios

    @patch("src.agent.tools.genai.Client")
    def test_successful_generation(self, mock_client_class: MagicMock) -> None:
        """Should return image data on successful generation."""
        # Mock the response structure
        mock_part = MagicMock()
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = b"fake_image_data"
        mock_part.inline_data.mime_type = "image/png"

        mock_candidate = MagicMock()
        mock_candidate.content = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 20
        mock_response.usage_metadata.thoughts_token_count = 5
        mock_response.usage_metadata.total_token_count = 35

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = generate_image.invoke({"prompt": "A beautiful sunset"})
        parsed = json.loads(result)

        assert parsed["success"] is True
        assert "_full_result" in parsed
        assert "image" in parsed["_full_result"]
        assert "data" in parsed["_full_result"]["image"]

    @patch("src.agent.tools.genai.Client")
    def test_includes_usage_metadata(self, mock_client_class: MagicMock) -> None:
        """Should include usage metadata for cost tracking."""
        mock_part = MagicMock()
        mock_part.inline_data = MagicMock()
        mock_part.inline_data.data = b"image"
        mock_part.inline_data.mime_type = "image/png"

        mock_candidate = MagicMock()
        mock_candidate.content = MagicMock()
        mock_candidate.content.parts = [mock_part]

        mock_response = MagicMock()
        mock_response.candidates = [mock_candidate]
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 200
        mock_response.usage_metadata.thoughts_token_count = 50
        mock_response.usage_metadata.total_token_count = 350

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = generate_image.invoke({"prompt": "test"})
        parsed = json.loads(result)

        assert "usage_metadata" in parsed
        assert parsed["usage_metadata"]["prompt_token_count"] == 100
        assert parsed["usage_metadata"]["candidates_token_count"] == 200

    @patch("src.agent.tools.genai.Client")
    def test_handles_no_candidates(self, mock_client_class: MagicMock) -> None:
        """Should return error when no candidates in response."""
        mock_response = MagicMock()
        mock_response.candidates = []
        mock_response.usage_metadata = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        result = generate_image.invoke({"prompt": "test"})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "No image generated" in parsed["error"]

    @patch("src.agent.tools.genai.Client")
    def test_handles_safety_block(self, mock_client_class: MagicMock) -> None:
        """Should return friendly error for safety blocks."""
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception(
            "SAFETY: Content blocked"
        )
        mock_client_class.return_value = mock_client

        result = generate_image.invoke({"prompt": "inappropriate content"})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "safety filters" in parsed["error"].lower()

    @patch("src.agent.tools.Config.MAX_IMAGE_PROMPT_LENGTH", 100)
    def test_rejects_too_long_prompt(self) -> None:
        """Should reject prompts exceeding max length."""
        long_prompt = "a" * 150
        result = generate_image.invoke({"prompt": long_prompt})
        parsed = json.loads(result)

        assert "error" in parsed
        assert "too long" in parsed["error"].lower()
