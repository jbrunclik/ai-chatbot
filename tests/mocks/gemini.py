"""Mock helpers for Gemini LLM responses."""

from typing import Any
from unittest.mock import MagicMock


def create_mock_ai_message(
    content: str = "Test response",
    tool_calls: list[dict[str, Any]] | None = None,
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> MagicMock:
    """Create a mock AIMessage with realistic structure.

    Args:
        content: The message content text
        tool_calls: Optional list of tool call dicts
        input_tokens: Number of input tokens for usage tracking
        output_tokens: Number of output tokens for usage tracking

    Returns:
        Mock AIMessage object
    """
    msg = MagicMock()
    msg.content = content
    msg.tool_calls = tool_calls or []
    msg.usage_metadata = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }
    return msg


def create_mock_ai_message_chunk(
    content: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> MagicMock:
    """Create mock AIMessageChunk for streaming tests.

    Args:
        content: The chunk content
        input_tokens: Input tokens (usually only in final chunk)
        output_tokens: Output tokens (usually only in final chunk)

    Returns:
        Mock AIMessageChunk object
    """
    chunk = MagicMock()
    chunk.content = content
    chunk.tool_calls = []
    chunk.tool_call_chunks = []
    chunk.usage_metadata = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
    return chunk


def create_mock_tool_message(content: str, tool_call_id: str = "test-id") -> MagicMock:
    """Create a mock ToolMessage.

    Args:
        content: The tool result content
        tool_call_id: The ID of the tool call this responds to

    Returns:
        Mock ToolMessage object
    """
    msg = MagicMock()
    msg.content = content
    msg.tool_call_id = tool_call_id
    return msg


def create_mock_tool_call_response(tool_name: str, tool_input: dict[str, Any]) -> MagicMock:
    """Create AIMessage with tool call request.

    Args:
        tool_name: Name of the tool to call
        tool_input: Arguments to pass to the tool

    Returns:
        Mock AIMessage with tool_calls populated
    """
    msg = MagicMock()
    msg.content = ""
    msg.tool_calls = [
        {
            "name": tool_name,
            "args": tool_input,
            "id": f"call-{tool_name}-123",
        }
    ]
    msg.usage_metadata = {"input_tokens": 50, "output_tokens": 20}
    return msg
