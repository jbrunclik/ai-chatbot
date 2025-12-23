"""Chat agent with tool support using LangGraph.

This module implements an agentic chat loop using LangGraph that supports tool calling.
The agent can use web search and URL fetching tools to answer questions about current events.

Architecture:
    The agent uses a cyclic graph pattern for tool calling:

    ┌─────────────────────────────────────────────────────┐
    │                                                     │
    │   Entry ──► Chat Node ──► Conditional Edge ──► END  │
    │                │                 │                  │
    │                │           (has tool calls?)        │
    │                │                 │                  │
    │                │                 ▼                  │
    │                └─────────── Tool Node               │
    │                                                     │
    └─────────────────────────────────────────────────────┘

Flow:
    1. User message is added to the conversation state
    2. Chat node invokes the LLM with the current messages
    3. If the LLM response contains tool calls:
       - Tool node executes the requested tools
       - Results are added as ToolMessages
       - Control returns to Chat node (step 2)
    4. If no tool calls, the response is returned to the user

Components:
    - AgentState: TypedDict holding conversation messages
    - ChatAgent: Main class with chat() and chat_with_state() methods
    - SYSTEM_PROMPT: Instructions for when to use web tools
    - extract_text_content(): Helper to handle Gemini's varied response formats:
        * str: Plain text responses (most common)
        * dict: Structured content like {'type': 'text', 'text': '...'}
        * list: Multi-part responses with tool calls, e.g.,
          [{'type': 'text', 'text': '...'}, {'type': 'tool_use', ...}]
          Also includes metadata like 'extras', 'signature' which are skipped
"""

import contextvars
import json
import re
from collections.abc import Generator
from datetime import datetime
from typing import Annotated, Any, Literal, TypedDict, cast

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode as BaseToolNode

from src.agent.tools import TOOLS
from src.config import Config
from src.utils.logging import get_logger

logger = get_logger(__name__)


def strip_full_result_from_tool_content(content: str) -> str:
    """Strip the _full_result field from tool result JSON to avoid sending large data to LLM.

    The generate_image tool returns image data in a _full_result field that should be
    extracted server-side but not sent back to the LLM (to avoid ~650K tokens of base64).

    Args:
        content: The tool result content (JSON string)

    Returns:
        The content with _full_result removed, or original content if not JSON
    """
    try:
        data = json.loads(content)
        if isinstance(data, dict) and "_full_result" in data:
            # Remove the _full_result field before sending to LLM
            data_for_llm = {k: v for k, v in data.items() if k != "_full_result"}
            return json.dumps(data_for_llm)
        return content
    except (json.JSONDecodeError, TypeError):
        return content


# Contextvar to hold the current request ID for tool result capture
# This allows us to capture full results per-request without passing request_id through the graph
_current_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "_current_request_id", default=None
)

# Global storage for full tool results before stripping (keyed by thread/request)
# This allows us to capture the full results for server-side extraction while
# still stripping them before sending to the LLM
_full_tool_results: dict[str, list[dict[str, Any]]] = {}


def set_current_request_id(request_id: str | None) -> None:
    """Set the current request ID for tool result capture."""
    _current_request_id.set(request_id)


def get_full_tool_results(request_id: str) -> list[dict[str, Any]]:
    """Get and clear full tool results for a request."""
    return _full_tool_results.pop(request_id, [])


def create_tool_node(tools: list[Any]) -> Any:
    """Create a tool node that strips large data from results before sending to LLM.

    This prevents the ~650K token cost of sending generated images back to the model.
    The full tool results are still captured separately for server-side extraction.

    The request ID is read from the _current_request_id contextvar at runtime,
    allowing per-request capture while using a single shared graph instance.

    Args:
        tools: List of tools to use
    """
    base_tool_node = BaseToolNode(tools)

    def tool_node_with_stripping(state: AgentState) -> dict[str, Any]:
        """Execute tools and strip _full_result from results."""
        logger.debug("tool_node_with_stripping starting")

        # Get the current request ID from contextvar
        request_id = _current_request_id.get()

        # Call the base ToolNode
        result: dict[str, Any] = base_tool_node.invoke(state)

        # Capture full tool results BEFORE stripping, then strip for LLM
        if "messages" in result:
            for msg in result["messages"]:
                if isinstance(msg, ToolMessage) and isinstance(msg.content, str):
                    # Store the ORIGINAL content for server-side extraction
                    if request_id is not None:
                        if request_id not in _full_tool_results:
                            _full_tool_results[request_id] = []
                        _full_tool_results[request_id].append(
                            {"type": "tool", "content": msg.content}
                        )

                    # Now strip _full_result for the LLM
                    content_len_before = len(msg.content)
                    msg.content = strip_full_result_from_tool_content(msg.content)
                    content_len_after = len(msg.content)
                    if content_len_before != content_len_after:
                        logger.info(
                            "Stripped _full_result from tool message",
                            extra={
                                "content_len_before": content_len_before,
                                "content_len_after": content_len_after,
                                "bytes_saved": content_len_before - content_len_after,
                            },
                        )

        logger.debug("tool_node_with_stripping completed")
        return result

    return tool_node_with_stripping


BASE_SYSTEM_PROMPT = """You are a helpful, harmless, and honest AI assistant.

# Core Principles
- Be direct and confident in your responses. Avoid unnecessary hedging or filler phrases.
- If you don't know something, say so clearly rather than making things up.
- When asked for opinions, you can share perspectives while noting they're your views.
- Match the user's tone and level of formality.
- For complex questions, think step-by-step before answering.

# Response Format
- Use markdown formatting when it improves readability (headers, lists, code blocks).
- Keep responses concise unless the user asks for detail.
- For code: include brief comments, use consistent style, handle edge cases.
- When showing multiple options, use numbered lists with pros/cons.

# Safety & Ethics
- Never help with illegal activities, harm, or deception.
- Protect user privacy; don't ask for unnecessary personal information.
- For medical, legal, or financial questions, recommend consulting professionals.
- If a request seems harmful, explain why you can't help and offer alternatives."""

TOOLS_SYSTEM_PROMPT = """
# Tools Available
You have access to the following tools:

## Web Tools
- **web_search**: Search the web for current information, news, prices, events, etc. Returns JSON with results.
- **fetch_url**: Fetch and read the content of a specific web page.

## Image Generation
- **generate_image**: Generate images from text descriptions. Returns JSON with the image data.

# CRITICAL: How to Use Tools Correctly
You have function calling capabilities. To use a tool:
1. Call the tool function directly (NOT by writing JSON in your text response)
2. The tool will execute and return results
3. Then write your natural language response to the user

WRONG (do NOT do this):
```
{"action": "generate_image", "action_input": {"prompt": "..."}}
```

RIGHT: Call the tool function directly, then write a response like:
"Here's the image I created for you..."

IMPORTANT RULES:
- NEVER write tool calls as JSON text in your response
- You MUST ALWAYS include a natural language response that the user can see
- After ANY tool call completes, you MUST write text to explain what happened
- If generating an image, ALWAYS respond with text like "Here's the image I created for you..." or "I've generated..."
- NEVER leave the response empty after using a tool - the user needs to see what you did

# When to Use Web Tools
ALWAYS use web_search first when the user asks about:
- Current events, news, "what happened today/recently"
- Real-time data: stock prices, crypto, weather, sports scores
- Recent releases, updates, or announcements
- Anything that might have changed since your training cutoff
- Facts you're uncertain about (verify before answering)

After searching, use fetch_url to read specific pages for more details if needed.
Do NOT rely on training data for time-sensitive information.

# When to Use Image Generation
Use generate_image when the user:
- Asks you to create, generate, draw, make, or produce an image
- Wants a visualization, illustration, or artwork
- Requests modifications to a previously generated image (describe the full desired result)

For image prompts, be specific and detailed:
- Include style (photorealistic, cartoon, watercolor, oil painting, etc.)
- Describe colors, lighting, composition, mood, and atmosphere
- If text should appear in the image, specify it clearly
- For modifications, describe the complete desired result, not just the changes

# Knowledge Cutoff
Your training data has a cutoff date. For anything after that, use web_search.

# Response Metadata
When you use ANY tools, you MUST append a SINGLE metadata block at the very end of your response.
IMPORTANT: There must be only ONE metadata block per response, even if you use multiple different tools.

Use this exact format with the special markers:
<!-- METADATA:
{"sources": [...], "generated_images": [...]}
-->

## Rules for Sources (web_search, fetch_url)
- Include ALL sources you referenced: both from web_search results AND any URLs you fetched with fetch_url
- Only include sources you actually used information from in your response
- Each source needs "title" and "url" fields
- For fetch_url sources, use the page title (or URL domain if unknown) as the title

## Rules for Generated Images (generate_image)
- Include the exact prompt you used to generate the image
- Each generated_images entry needs: {"prompt": "the exact prompt you used"}

## General Metadata Rules
- Do NOT include this section if you didn't use any tools
- The JSON must be valid - use double quotes, escape special characters
- If you used BOTH web tools AND generate_image, include BOTH "sources" and "generated_images" arrays in the SAME metadata block
- Do NOT create separate metadata blocks for different tools - combine everything into ONE block

Example with both sources and generated images:
<!-- METADATA:
{"sources": [{"title": "Wikipedia", "url": "https://en.wikipedia.org/..."}], "generated_images": [{"prompt": "a majestic mountain sunset, photorealistic, golden hour lighting"}]}
-->

Example with only sources:
<!-- METADATA:
{"sources": [{"title": "Wikipedia", "url": "https://en.wikipedia.org/..."}]}
-->

Example with only generated images:
<!-- METADATA:
{"generated_images": [{"prompt": "a majestic mountain sunset, photorealistic, golden hour lighting"}]}
-->"""


def get_force_tools_prompt(force_tools: list[str]) -> str:
    """Build a prompt instructing the LLM to use specific tools.

    Args:
        force_tools: List of tool names to force (e.g., ["web_search"])

    Returns:
        A formatted instruction string
    """
    tool_list = "\n".join(f"- {tool}" for tool in force_tools)
    return f"""
# IMPORTANT: Mandatory Tool Usage
Before responding to this query, you MUST use the following tools:
{tool_list}

Call each required tool first, then provide your response based on the results. Do not skip this step."""


def get_system_prompt(with_tools: bool = True, force_tools: list[str] | None = None) -> str:
    """Build the system prompt, optionally including tool instructions.

    Args:
        with_tools: Whether tools are available
        force_tools: List of tool names that must be used (e.g., ["web_search", "image_generation"])
    """
    date_context = f"\n\nCurrent date and time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    prompt = BASE_SYSTEM_PROMPT
    if with_tools and TOOLS:
        prompt += TOOLS_SYSTEM_PROMPT

    # Add force tools instruction if specified
    if force_tools:
        prompt += get_force_tools_prompt(force_tools)

    return prompt + date_context


def extract_text_content(content: str | list[Any] | dict[str, Any]) -> str:
    """Extract text from message content, handling various formats from Gemini."""
    if isinstance(content, str):
        return content

    # Handle dict format (e.g., {'type': 'text', 'text': '...'})
    if isinstance(content, dict):
        if content.get("type") == "text":
            return str(content.get("text", ""))
        # If it has a 'text' key directly, use that
        if "text" in content:
            return str(content["text"])
        # Otherwise skip non-text content
        return ""

    # Handle list format from Gemini (e.g., [{'type': 'text', 'text': '...'}])
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                # Extract text from dict, skip 'extras' and other metadata
                if part.get("type") == "text":
                    text_parts.append(str(part.get("text", "")))
                elif "text" in part and "type" not in part:
                    text_parts.append(str(part["text"]))
                # Skip parts with 'extras', 'signature', etc.
            elif isinstance(part, str):
                text_parts.append(part)
        return "".join(text_parts)

    return str(content)


# Pattern to match metadata block: <!-- METADATA:\n{...}\n-->
METADATA_PATTERN = re.compile(
    r"<!--\s*METADATA:\s*\n(.*?)\n\s*-->",
    re.DOTALL | re.IGNORECASE,
)


# Pattern to match Gemini's tool call JSON format that sometimes leaks into response text
# This happens when the model outputs the tool call description as text alongside the actual tool call
# Format: {"action": "tool_name", "action_input": "..."} or {"action": "tool_name", "action_input": {...}}
# Note: Properly handles escaped quotes in string values. For object values, matches balanced braces
# up to 2 levels deep (sufficient for typical tool call artifacts like {"prompt": "..."}).
# The pattern is specific enough (requires "action" and "action_input" keys) to avoid false matches.
TOOL_CALL_JSON_PATTERN = re.compile(
    r'\n*\{\s*"action":\s*"(?:[^"\\]|\\.)+"\s*,\s*"action_input":\s*(?:"(?:[^"\\]|\\.)*"|\{(?:[^{}]|\{[^}]*\})*\})\s*\}',
    re.DOTALL,
)


def clean_tool_call_json(response: str) -> str:
    """Remove tool call JSON artifacts that sometimes leak into LLM response text.

    Gemini may output tool call descriptions as text alongside actual function calls.
    This removes those JSON blocks to keep only natural language content.

    Args:
        response: The LLM response text

    Returns:
        Response with tool call JSON removed
    """
    return TOOL_CALL_JSON_PATTERN.sub("", response).strip()


def _find_json_object_end(text: str, start_pos: int) -> int | None:
    """Find the end position of a complete JSON object starting at start_pos.

    Returns the position after the closing brace, or None if not found.
    """
    brace_count = 0
    in_string = False
    escape_next = False

    for i in range(start_pos, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == "\\":
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            brace_count += 1
        elif char == "}":
            brace_count -= 1
            if brace_count == 0:
                return i + 1

    return None


def extract_metadata_from_response(response: str) -> tuple[str, dict[str, Any]]:
    """Extract metadata from LLM response and return clean content.

    The LLM is instructed to append metadata at the end of responses in the format:
    <!-- METADATA:
    {"sources": [...]}
    -->

    However, sometimes the LLM outputs plain JSON without the HTML comment wrapper,
    or outputs it in both formats. This function prefers the HTML comment format,
    but removes both if they both exist.

    Also removes any tool call JSON artifacts that leaked into the response.

    Args:
        response: The raw LLM response text

    Returns:
        Tuple of (clean_content, metadata_dict)
        - clean_content: Response with metadata block and tool call JSON removed
        - metadata_dict: Parsed metadata (empty dict if none found or parse error)
    """
    response = clean_tool_call_json(response)
    metadata: dict[str, Any] = {}
    clean_content = response

    # Try HTML comment format first (preferred format)
    match = METADATA_PATTERN.search(clean_content)
    if match:
        try:
            metadata = json.loads(match.group(1).strip())
            clean_content = clean_content[: match.start()].rstrip()
        except (json.JSONDecodeError, AttributeError):
            # If parsing fails, continue to check for plain JSON
            pass

    # Also check for plain JSON metadata and remove it (even if we already found HTML comment)
    # This ensures we remove both if the LLM outputs metadata in both formats
    # Search backwards for JSON objects that might contain metadata
    # We need to find the outermost object, so we search from the end
    search_start = len(clean_content)
    while True:
        # Find the last opening brace before our search start
        last_brace = clean_content.rfind("{", 0, search_start)
        if last_brace == -1:
            break

        end_pos = _find_json_object_end(clean_content, last_brace)
        if end_pos:
            try:
                parsed = json.loads(clean_content[last_brace:end_pos])
                if "sources" in parsed or "generated_images" in parsed:
                    # Only use this metadata if we didn't already get it from HTML comment
                    if not metadata:
                        metadata = parsed
                    # Remove the JSON from response regardless
                    clean_content = clean_content[:last_brace].rstrip()
                    break
            except (json.JSONDecodeError, ValueError):
                pass

        # Continue searching backwards from before this brace
        search_start = last_brace

    return clean_content.rstrip(), metadata


class AgentState(TypedDict):
    """State for the chat agent."""

    messages: Annotated[list[BaseMessage], add_messages]


def create_chat_model(model_name: str, with_tools: bool = True) -> ChatGoogleGenerativeAI:
    """Create a Gemini chat model, optionally with tools bound."""
    model = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=Config.GEMINI_API_KEY,
        temperature=1.0,  # Recommended default for Gemini 3
        convert_system_message_to_human=True,
    )

    if with_tools and TOOLS:
        return model.bind_tools(TOOLS)  # type: ignore[return-value]

    return model


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """Decide whether to continue to tools or end the conversation."""
    messages = state["messages"]
    last_message = messages[-1]

    # If the last message has tool calls, continue to tools
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"

    return "end"


def chat_node(state: AgentState, model: ChatGoogleGenerativeAI) -> dict[str, list[BaseMessage]]:
    """Process messages and generate a response."""
    messages = state["messages"]
    message_count = len(messages)
    logger.debug(
        "Invoking LLM",
        extra={
            "message_count": message_count,
            "model": model.model_name if hasattr(model, "model_name") else "unknown",
        },
    )
    response = model.invoke(messages)

    # Log tool calls if present
    if isinstance(response, AIMessage) and response.tool_calls:
        tool_names = [tc.get("name", "unknown") for tc in response.tool_calls]
        logger.info(
            "LLM requested tool calls",
            extra={"tool_calls": tool_names, "count": len(response.tool_calls)},
        )
    else:
        logger.debug("LLM response received", extra={"has_content": bool(response.content)})

    # Log usage metadata if available
    # Note: usage_metadata is a direct attribute, not in response_metadata
    if isinstance(response, AIMessage):
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            logger.debug(
                "Usage metadata captured",
                extra={
                    "input_tokens": usage.get("input_tokens", 0),
                    "output_tokens": usage.get("output_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            )
        else:
            logger.debug("No usage_metadata attribute found on AIMessage")

    return {"messages": [response]}


def create_chat_graph(model_name: str, with_tools: bool = True) -> StateGraph[AgentState]:
    """Create a chat graph with optional tool support."""
    model = create_chat_model(model_name, with_tools=with_tools)

    # Define the graph
    graph: StateGraph[AgentState] = StateGraph(AgentState)

    # Add the chat node
    graph.add_node("chat", lambda state: chat_node(state, model))

    if with_tools and TOOLS:
        # Add tool node with stripping of large results
        tool_node = create_tool_node(TOOLS)
        graph.add_node("tools", tool_node)

        # Set entry point
        graph.set_entry_point("chat")

        # Add conditional edge based on whether to use tools
        graph.add_conditional_edges("chat", should_continue, {"tools": "tools", "end": END})

        # After tools, go back to chat
        graph.add_edge("tools", "chat")
    else:
        # Simple graph without tools
        graph.set_entry_point("chat")
        graph.add_edge("chat", END)

    return graph


class ChatAgent:
    """Agent for handling chat conversations with tool support."""

    def __init__(self, model_name: str = Config.DEFAULT_MODEL, with_tools: bool = True) -> None:
        self.model_name = model_name
        self.with_tools = with_tools
        logger.debug("Creating ChatAgent", extra={"model": model_name, "with_tools": with_tools})
        self.graph = create_chat_graph(model_name, with_tools=with_tools).compile()

    def _build_message_content(
        self, text: str, files: list[dict[str, Any]] | None = None
    ) -> str | list[str | dict[Any, Any]]:
        """Build message content for LangChain.

        Args:
            text: Plain text message
            files: Optional list of file attachments

        Returns:
            For text-only: the string
            For multimodal: list of content blocks for LangChain
        """
        if not files:
            return text

        # Build multimodal content blocks
        blocks: list[str | dict[Any, Any]] = []

        # Add text block if present
        if text:
            blocks.append({"type": "text", "text": text})

        # Add file blocks
        for file in files:
            mime_type = file.get("type", "application/octet-stream")
            data = file.get("data", "")

            if mime_type.startswith("image/"):
                # Image block for Gemini
                blocks.append(
                    {
                        "type": "image",
                        "base64": data,
                        "mime_type": mime_type,
                    }
                )
            elif mime_type == "application/pdf":
                # PDF - Gemini supports inline PDFs
                blocks.append(
                    {
                        "type": "image",  # LangChain uses image type for PDFs too
                        "base64": data,
                        "mime_type": mime_type,
                    }
                )
            else:
                # Text files - include as text block
                try:
                    import base64

                    decoded = base64.b64decode(data).decode("utf-8")
                    file_name = file.get("name", "file")
                    blocks.append(
                        {
                            "type": "text",
                            "text": f"\n--- Content of {file_name} ---\n{decoded}\n--- End of {file_name} ---\n",
                        }
                    )
                except Exception:
                    # If decoding fails, skip the file
                    pass

        return blocks if blocks else text

    def _build_messages(
        self,
        text: str,
        files: list[dict[str, Any]] | None = None,
        history: list[dict[str, Any]] | None = None,
        force_tools: list[str] | None = None,
    ) -> list[BaseMessage]:
        """Build the messages list from history and user message."""
        messages: list[BaseMessage] = []

        # Always add system prompt (with tool instructions if tools are enabled)
        messages.append(
            SystemMessage(content=get_system_prompt(self.with_tools, force_tools=force_tools))
        )

        if history:
            for msg in history:
                if msg["role"] == "user":
                    content = self._build_message_content(msg["content"], msg.get("files"))
                    messages.append(HumanMessage(content=content))
                elif msg["role"] == "assistant":
                    # Assistant messages are always text
                    messages.append(AIMessage(content=msg["content"]))

        # Add the current user message
        content = self._build_message_content(text, files)
        messages.append(HumanMessage(content=content))

        return messages

    def chat(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> str:
        """
        Send a message and get a response.

        Args:
            user_message: The user's message
            history: Optional list of previous messages with 'role' and 'content' keys

        Returns:
            The assistant's response text
        """
        messages = self._build_messages(user_message, history)

        # Run the graph
        result = self.graph.invoke(cast(Any, {"messages": messages}))

        # Extract the assistant's response (last AI message without tool calls)
        response_text = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                # Skip messages that only have tool calls
                if msg.tool_calls and not extract_text_content(msg.content):
                    continue
                response_text = extract_text_content(msg.content)
                break

        return response_text

    def stream_chat(
        self,
        text: str,
        files: list[dict[str, Any]] | None = None,
        history: list[dict[str, Any]] | None = None,
        force_tools: list[str] | None = None,
    ) -> Generator[
        str | tuple[str, dict[str, Any], list[dict[str, Any]], dict[str, Any]], None, None
    ]:
        """
        Stream response tokens using LangGraph's stream method.

        Args:
            text: The user's message text
            files: Optional list of file attachments
            history: Optional list of previous messages with 'role', 'content', and 'files' keys
            force_tools: Optional list of tool names that must be used

        Yields:
            - str: Text tokens for streaming display
            - tuple: Final (content, metadata, tool_results, usage_info) where:
              - content: Clean response text (metadata stripped)
              - metadata: Extracted metadata dict (sources, generated_images, etc.)
              - tool_results: List of tool message dicts for server-side processing
              - usage_info: Dict with 'input_tokens' and 'output_tokens'
        """
        messages = self._build_messages(text, files, history, force_tools=force_tools)

        # Accumulate full response to extract metadata at the end
        full_response = ""
        # Buffer to detect metadata marker - we hold back chars until we're sure
        # they're not part of the metadata marker
        buffer = ""
        metadata_marker = "<!-- METADATA:"
        in_metadata = False
        # Capture tool results for server-side extraction (e.g., generated images)
        tool_results: list[dict[str, Any]] = []
        # Track token counts as we stream (memory efficient - only store numbers, not message objects)
        total_input_tokens = 0
        total_output_tokens = 0
        chunk_count = 0

        # Stream the graph execution with messages mode for token-level streaming
        for event in self.graph.stream(
            cast(Any, {"messages": messages}),
            stream_mode="messages",
        ):
            # event is a tuple of (message_chunk, metadata) in messages mode
            if isinstance(event, tuple) and len(event) >= 1:
                message_chunk = event[0]

                # Capture tool messages (results from tool execution)
                if isinstance(message_chunk, ToolMessage):
                    tool_results.append(
                        {
                            "type": "tool",
                            "content": message_chunk.content,
                        }
                    )
                    continue

                # Only yield content from AI message chunks (not tool calls or tool results)
                if isinstance(message_chunk, AIMessageChunk):
                    # Extract usage metadata immediately (don't store the message object)
                    chunk_count += 1
                    if hasattr(message_chunk, "usage_metadata") and message_chunk.usage_metadata:
                        usage = message_chunk.usage_metadata
                        if isinstance(usage, dict):
                            input_tokens = usage.get("input_tokens", 0)
                            output_tokens = usage.get("output_tokens", 0)
                            if input_tokens > 0 or output_tokens > 0:
                                total_input_tokens += input_tokens
                                total_output_tokens += output_tokens
                                logger.debug(
                                    "Found usage in chunk",
                                    extra={
                                        "input_tokens": input_tokens,
                                        "output_tokens": output_tokens,
                                    },
                                )

                    # Skip chunks that are only tool calls (no text content)
                    if message_chunk.tool_calls or message_chunk.tool_call_chunks:
                        continue
                    if message_chunk.content:
                        content = extract_text_content(message_chunk.content)
                        if content:
                            full_response += content

                            # If we've detected metadata, don't yield anything more
                            if in_metadata:
                                continue

                            # Add to buffer and check for metadata marker
                            buffer += content

                            # Check if buffer contains the start of metadata (HTML comment format)
                            if metadata_marker in buffer:
                                # Yield everything before the marker
                                marker_pos = buffer.find(metadata_marker)
                                if marker_pos > 0:
                                    yield buffer[:marker_pos].rstrip()
                                in_metadata = True
                                buffer = ""
                            elif len(buffer) > len(metadata_marker):
                                # Buffer is longer than marker, safe to yield the excess
                                safe_length = len(buffer) - len(metadata_marker)
                                yield buffer[:safe_length]
                                buffer = buffer[safe_length:]

        # Yield any remaining buffer that's not metadata
        if buffer and not in_metadata:
            # Final check - might end with partial marker or JSON
            clean, _ = extract_metadata_from_response(buffer)
            if clean and clean.strip():
                yield clean

        # Extract metadata and yield final tuple
        clean_content, metadata = extract_metadata_from_response(full_response)

        # Log a warning if we didn't find any usage metadata (should be rare)
        if total_input_tokens == 0 and total_output_tokens == 0 and chunk_count > 0:
            logger.warning(
                "No usage metadata found in streaming chunks",
                extra={
                    "chunk_count": chunk_count,
                    "note": "This is unusual - Gemini streaming chunks typically include usage_metadata. Cost tracking may be inaccurate for this request.",
                },
            )

        usage_info = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        }

        if total_input_tokens > 0 or total_output_tokens > 0:
            logger.debug(
                "Usage metadata aggregated from streaming chunks",
                extra={
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                    "chunk_count": chunk_count,
                },
            )

        # Final yield: (content, metadata, tool_results, usage_info) for server processing
        yield (clean_content, metadata, tool_results, usage_info)

    def chat_with_state(
        self,
        text: str,
        files: list[dict[str, Any]] | None = None,
        previous_state: dict[str, Any] | None = None,
        force_tools: list[str] | None = None,
    ) -> tuple[str, dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
        """
        Chat with persistent state for multi-turn agent workflows.

        Args:
            text: The user's message text
            files: Optional list of file attachments
            previous_state: Optional previous agent state
            force_tools: Optional list of tool names that must be used

        Returns:
            Tuple of (response text, new state for persistence, tool results, usage info)
            - response text: The assistant's response
            - new state: State for persistence
            - tool results: Tool execution results (not persisted)
            - usage_info: Dict with 'input_tokens' and 'output_tokens'
        """
        # Restore previous messages or start fresh
        messages: list[BaseMessage] = []

        # Always add system prompt (with tool instructions if tools are enabled)
        messages.append(
            SystemMessage(content=get_system_prompt(self.with_tools, force_tools=force_tools))
        )

        if previous_state and "messages" in previous_state:
            history_count = len(previous_state["messages"])
            logger.debug("Restoring agent state", extra={"history_message_count": history_count})
            for msg_data in previous_state["messages"]:
                if msg_data["type"] == "human":
                    messages.append(HumanMessage(content=msg_data["content"]))
                elif msg_data["type"] == "ai":
                    messages.append(AIMessage(content=msg_data["content"]))
                # Skip tool messages - they are no longer persisted and shouldn't
                # be restored (prevents issues with large binary data and tool reuse)

        # Add the current user message (with multimodal support)
        content = self._build_message_content(text, files)
        messages.append(HumanMessage(content=content))
        logger.debug(
            "Starting chat_with_state",
            extra={
                "model": self.model_name,
                "message_length": len(text),
                "has_files": bool(files),
                "file_count": len(files) if files else 0,
                "force_tools": force_tools,
                "total_messages": len(messages),
            },
        )

        # Run the graph
        result = self.graph.invoke(cast(Any, {"messages": messages}))

        # Extract response (last AI message with actual content)
        # We need to find the final AI response that has text content.
        # This might be after tool calls, so we iterate in reverse and take the
        # first AIMessage that has extractable text content (even if it also has tool_calls).
        response_text = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                # Extract text content first to see if there's any text
                text = extract_text_content(msg.content)
                # Skip if this message only has tool calls and no text content
                if msg.tool_calls and not text:
                    continue
                # Clean any tool call JSON that leaked into response
                text = clean_tool_call_json(text)
                if text:
                    response_text = text
                    break

        # Extract tool results from the raw result (before state serialization)
        # These are returned separately for server-side processing (e.g., extracting images)
        tool_results: list[dict[str, Any]] = []
        for msg in result["messages"]:
            if isinstance(msg, ToolMessage):
                tool_results.append(
                    {
                        "type": "tool",
                        "content": msg.content,
                    }
                )

        if tool_results:
            logger.info("Tool results captured", extra={"tool_result_count": len(tool_results)})

        # Aggregate usage metadata from all AIMessages
        # Note: usage_metadata is a direct attribute on AIMessage, not in response_metadata
        total_input_tokens = 0
        total_output_tokens = 0
        for msg in result["messages"]:
            if isinstance(msg, AIMessage):
                # Check usage_metadata as a direct attribute (this is where LangChain puts it)
                if hasattr(msg, "usage_metadata") and msg.usage_metadata:
                    usage = msg.usage_metadata
                    if isinstance(usage, dict):
                        # Gemini provides input_tokens and output_tokens directly
                        input_tokens = usage.get("input_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0)

                        if input_tokens > 0 or output_tokens > 0:
                            total_input_tokens += input_tokens
                            total_output_tokens += output_tokens
                            logger.debug(
                                "Found usage metadata in AIMessage",
                                extra={
                                    "input_tokens": input_tokens,
                                    "output_tokens": output_tokens,
                                },
                            )

        usage_info = {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
        }

        if total_input_tokens > 0 or total_output_tokens > 0:
            logger.debug(
                "Usage metadata aggregated",
                extra={
                    "input_tokens": total_input_tokens,
                    "output_tokens": total_output_tokens,
                },
            )

        # Serialize state for persistence
        # NOTE: We exclude ToolMessages from persisted state because:
        # 1. Tool results (especially generate_image) can contain large binary data
        # 2. Preserving tool results may cause the LLM to skip calling tools again
        # 3. For multi-turn conversations, the LLM has the conversation context from
        #    human/ai messages which is sufficient for continuity
        new_state: dict[str, Any] = {"messages": []}
        for m in result["messages"]:
            if isinstance(m, HumanMessage):
                new_state["messages"].append(
                    {"type": "human", "content": extract_text_content(m.content)}
                )
            elif isinstance(m, AIMessage):
                content = extract_text_content(m.content)
                # Clean any tool call JSON that leaked into the response
                content = clean_tool_call_json(content)
                if content:  # Only store if there's actual content after cleaning
                    new_state["messages"].append({"type": "ai", "content": content})
            # Skip ToolMessages - they contain execution details that shouldn't persist

        return response_text, new_state, tool_results, usage_info


def generate_title(user_message: str, assistant_response: str) -> str:
    """
    Generate a concise title for a conversation using Gemini.

    Args:
        user_message: The first user message
        assistant_response: The assistant's response

    Returns:
        A short, descriptive title (max ~50 chars)
    """
    logger.debug("Generating conversation title")
    # Use Flash model for fast, cheap title generation
    model = ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=Config.GEMINI_API_KEY,
        temperature=0.7,
    )

    prompt = f"""Generate a very short, concise title (3-6 words max) for this conversation.
The title should capture the main topic or intent.
Do NOT use quotes around the title.
Do NOT include prefixes like "Title:" or "Topic:".
Just output the title text directly.

User: {user_message[:500]}
Assistant: {assistant_response[:500]}

Title:"""

    try:
        response = model.invoke([HumanMessage(content=prompt)])
        title = extract_text_content(response.content).strip()
        # Clean up any quotes or prefixes that slipped through
        title = title.strip("\"'")
        if title.lower().startswith("title:"):
            title = title[6:].strip()
        # Truncate if too long
        if len(title) > 60:
            title = title[:57] + "..."
        final_title = title or user_message[:50]
        logger.debug("Title generated", extra={"title": final_title})
        return final_title
    except Exception as e:
        # Fallback to truncated message on any error
        logger.warning("Title generation failed, using fallback", extra={"error": str(e)})
        return user_message[:50] + ("..." if len(user_message) > 50 else "")
