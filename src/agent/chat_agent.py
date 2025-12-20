from typing import Annotated, Any, TypedDict, cast

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from src.config import Config


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


class AgentState(TypedDict):
    """State for the chat agent."""

    messages: Annotated[list[BaseMessage], add_messages]


def create_chat_model(model_name: str) -> ChatGoogleGenerativeAI:
    """Create a Gemini chat model."""
    return ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=Config.GEMINI_API_KEY,
        temperature=1.0,  # Recommended default for Gemini 3
        convert_system_message_to_human=True,
    )


def chat_node(state: AgentState, model: ChatGoogleGenerativeAI) -> dict[str, list[BaseMessage]]:
    """Process messages and generate a response."""
    messages = state["messages"]
    response = model.invoke(messages)
    return {"messages": [response]}


def create_chat_graph(model_name: str) -> StateGraph[AgentState]:
    """Create a simple chat graph for conversation."""
    model = create_chat_model(model_name)

    # Define the graph
    graph: StateGraph[AgentState] = StateGraph(AgentState)

    # Add the chat node
    graph.add_node("chat", lambda state: chat_node(state, model))

    # Set entry point
    graph.set_entry_point("chat")

    # Connect to end
    graph.add_edge("chat", END)

    return graph


class ChatAgent:
    """Agent for handling chat conversations."""

    def __init__(self, model_name: str = Config.DEFAULT_MODEL) -> None:
        self.model_name = model_name
        self.graph = create_chat_graph(model_name).compile()

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
        # Convert history to LangChain messages
        messages: list[BaseMessage] = []
        if history:
            for msg in history:
                if msg["role"] == "user":
                    messages.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AIMessage(content=msg["content"]))

        # Add the current user message
        messages.append(HumanMessage(content=user_message))

        # Run the graph
        result = self.graph.invoke(cast(Any, {"messages": messages}))

        # Extract the assistant's response
        last_message = result["messages"][-1]
        return extract_text_content(last_message.content)

    def chat_with_state(
        self,
        user_message: str,
        previous_state: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """
        Chat with persistent state for multi-turn agent workflows.

        Args:
            user_message: The user's message
            previous_state: Optional previous agent state

        Returns:
            Tuple of (response text, new state for persistence)
        """
        # Restore previous messages or start fresh
        messages: list[BaseMessage] = []
        if previous_state and "messages" in previous_state:
            for msg_data in previous_state["messages"]:
                if msg_data["type"] == "human":
                    messages.append(HumanMessage(content=msg_data["content"]))
                elif msg_data["type"] == "ai":
                    messages.append(AIMessage(content=msg_data["content"]))

        # Add the current user message
        messages.append(HumanMessage(content=user_message))

        # Run the graph
        result = self.graph.invoke(cast(Any, {"messages": messages}))

        # Extract response
        last_message = result["messages"][-1]
        response = extract_text_content(last_message.content)

        # Serialize state for persistence
        new_state = {
            "messages": [
                {
                    "type": "human" if isinstance(m, HumanMessage) else "ai",
                    "content": extract_text_content(m.content),
                }
                for m in result["messages"]
            ]
        }

        return response, new_state
