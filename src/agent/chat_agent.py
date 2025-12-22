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
from langgraph.prebuilt import ToolNode

from src.agent.tools import TOOLS
from src.config import Config

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
You have access to web tools for real-time information:
- **web_search**: Search the web for current information, news, prices, events, etc. Returns JSON with results.
- **fetch_url**: Fetch and read the content of a specific web page.

# When to Use Tools
ALWAYS use web_search first when the user asks about:
- Current events, news, "what happened today/recently"
- Real-time data: stock prices, crypto, weather, sports scores
- Recent releases, updates, or announcements
- Anything that might have changed since your training cutoff
- Facts you're uncertain about (verify before answering)

After searching, use fetch_url to read specific pages for more details if needed.
Do NOT rely on training data for time-sensitive information.

# Knowledge Cutoff
Your training data has a cutoff date. For anything after that, use web_search.

# Response Metadata
When you use web tools (web_search or fetch_url), you MUST append metadata at the very end of your response.
Use this exact format with the special markers:

<!-- METADATA:
{"sources": [{"title": "Source Title", "url": "https://example.com"}]}
-->

Rules:
- Include ALL sources you referenced: both from web_search results AND any URLs you fetched with fetch_url
- Only include sources you actually used information from in your response
- Do NOT include this section if you didn't use any web tools
- The JSON must be valid - use double quotes, escape special characters
- Each source needs "title" and "url" fields
- For fetch_url sources, use the page title (or URL domain if unknown) as the title"""


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


def extract_metadata_from_response(response: str) -> tuple[str, dict[str, Any]]:
    """Extract metadata from LLM response and return clean content.

    The LLM is instructed to append metadata at the end of responses in the format:
    <!-- METADATA:
    {"sources": [...]}
    -->

    Args:
        response: The raw LLM response text

    Returns:
        Tuple of (clean_content, metadata_dict)
        - clean_content: Response with metadata block removed
        - metadata_dict: Parsed metadata (empty dict if none found or parse error)
    """
    match = METADATA_PATTERN.search(response)
    if not match:
        return response, {}

    try:
        metadata_json = match.group(1).strip()
        metadata = json.loads(metadata_json)

        # Remove the metadata block from the response
        clean_content = response[: match.start()].rstrip()

        return clean_content, metadata
    except (json.JSONDecodeError, AttributeError):
        # If parsing fails, return original response with empty metadata
        return response, {}


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
    response = model.invoke(messages)
    return {"messages": [response]}


def create_chat_graph(model_name: str, with_tools: bool = True) -> StateGraph[AgentState]:
    """Create a chat graph with optional tool support."""
    model = create_chat_model(model_name, with_tools=with_tools)

    # Define the graph
    graph: StateGraph[AgentState] = StateGraph(AgentState)

    # Add the chat node
    graph.add_node("chat", lambda state: chat_node(state, model))

    if with_tools and TOOLS:
        # Add tool node
        tool_node = ToolNode(TOOLS)
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
    ) -> Generator[str | tuple[str, list[dict[str, str]]], None, None]:
        """
        Stream response tokens using LangGraph's stream method.

        Args:
            text: The user's message text
            files: Optional list of file attachments
            history: Optional list of previous messages with 'role', 'content', and 'files' keys
            force_tools: Optional list of tool names that must be used

        Yields:
            Text tokens as they are generated.
            The final yield is a tuple of (full_content, sources) after metadata extraction.
        """
        messages = self._build_messages(text, files, history, force_tools=force_tools)

        # Accumulate full response to extract metadata at the end
        full_response = ""
        # Buffer to detect metadata marker - we hold back chars until we're sure
        # they're not part of the metadata marker
        buffer = ""
        metadata_marker = "<!-- METADATA:"
        in_metadata = False

        # Stream the graph execution with messages mode for token-level streaming
        for event in self.graph.stream(
            cast(Any, {"messages": messages}),
            stream_mode="messages",
        ):
            # event is a tuple of (message_chunk, metadata) in messages mode
            if isinstance(event, tuple) and len(event) >= 1:
                message_chunk = event[0]
                # Only yield content from AI message chunks (not tool calls or tool results)
                if isinstance(message_chunk, AIMessageChunk):
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

                            # Check if buffer contains the start of metadata
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
            # Final check - might end with partial marker
            if not buffer.rstrip().endswith("<!--"):
                clean, _ = extract_metadata_from_response(buffer)
                if clean:
                    yield clean

        # Extract metadata and yield final result with sources
        clean_content, metadata = extract_metadata_from_response(full_response)
        sources = metadata.get("sources", [])

        # Yield final tuple with clean content and sources
        yield (clean_content, sources)

    def chat_with_state(
        self,
        text: str,
        files: list[dict[str, Any]] | None = None,
        previous_state: dict[str, Any] | None = None,
        force_tools: list[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Chat with persistent state for multi-turn agent workflows.

        Args:
            text: The user's message text
            files: Optional list of file attachments
            previous_state: Optional previous agent state
            force_tools: Optional list of tool names that must be used

        Returns:
            Tuple of (response text, new state for persistence)
        """
        # Restore previous messages or start fresh
        messages: list[BaseMessage] = []

        # Always add system prompt (with tool instructions if tools are enabled)
        messages.append(
            SystemMessage(content=get_system_prompt(self.with_tools, force_tools=force_tools))
        )

        if previous_state and "messages" in previous_state:
            for msg_data in previous_state["messages"]:
                if msg_data["type"] == "human":
                    messages.append(HumanMessage(content=msg_data["content"]))
                elif msg_data["type"] == "ai":
                    messages.append(AIMessage(content=msg_data["content"]))
                elif msg_data["type"] == "tool":
                    messages.append(
                        ToolMessage(
                            content=msg_data["content"],
                            tool_call_id=msg_data.get("tool_call_id", ""),
                        )
                    )

        # Add the current user message (with multimodal support)
        content = self._build_message_content(text, files)
        messages.append(HumanMessage(content=content))

        # Run the graph
        result = self.graph.invoke(cast(Any, {"messages": messages}))

        # Extract response (last AI message with actual content)
        response_text = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                if msg.tool_calls and not extract_text_content(msg.content):
                    continue
                response_text = extract_text_content(msg.content)
                break

        # Serialize state for persistence (includes tool messages for multi-turn tool workflows)
        new_state: dict[str, Any] = {"messages": []}
        for m in result["messages"]:
            if isinstance(m, HumanMessage):
                new_state["messages"].append(
                    {"type": "human", "content": extract_text_content(m.content)}
                )
            elif isinstance(m, AIMessage):
                content = extract_text_content(m.content)
                if content:  # Only store if there's actual content
                    new_state["messages"].append({"type": "ai", "content": content})
            elif isinstance(m, ToolMessage):
                new_state["messages"].append(
                    {
                        "type": "tool",
                        "content": m.content,
                        "tool_call_id": m.tool_call_id,
                    }
                )

        return response_text, new_state


def generate_title(user_message: str, assistant_response: str) -> str:
    """
    Generate a concise title for a conversation using Gemini.

    Args:
        user_message: The first user message
        assistant_response: The assistant's response

    Returns:
        A short, descriptive title (max ~50 chars)
    """
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
        return title or user_message[:50]
    except Exception:
        # Fallback to truncated message on any error
        return user_message[:50] + ("..." if len(user_message) > 50 else "")
