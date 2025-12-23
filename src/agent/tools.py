"""Web tools for the AI agent."""

import base64
import json

import html2text
import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from google import genai
from google.genai import types
from langchain_core.tools import tool

from src.config import Config


def _extract_text_from_html(html: str, max_length: int = 15000) -> str:
    """Extract readable text from HTML content."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove script, style, nav, footer, header elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        element.decompose()

    # Convert to markdown
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = True
    converter.ignore_emphasis = False
    converter.body_width = 0  # No wrapping

    text = converter.handle(str(soup))

    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length] + "\n\n[Content truncated...]"

    return text.strip()


@tool
def fetch_url(url: str) -> str:
    """Fetch and extract text content from a URL.

    Use this tool to read the content of a web page. Returns the main text
    content in markdown format, or JSON with an error field if the fetch fails.

    Args:
        url: The URL to fetch (must start with http:// or https://)

    Returns:
        The text content of the page in markdown format, or JSON with error field
    """
    if not url.startswith(("http://", "https://")):
        return json.dumps(
            {"error": f"Invalid URL '{url}'. URL must start with http:// or https://"}
        )

    try:
        with httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
        ) as client:
            response = client.get(url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return json.dumps({"error": f"URL returned non-text content type: {content_type}"})

            return _extract_text_from_html(response.text)

    except httpx.TimeoutException:
        return json.dumps({"error": f"Request to {url} timed out"})
    except httpx.HTTPStatusError as e:
        return json.dumps({"error": f"HTTP {e.response.status_code} when fetching {url}"})
    except httpx.RequestError as e:
        return json.dumps({"error": f"Failed to fetch {url}: {e}"})


@tool
def web_search(query: str, num_results: int = 5) -> str:
    """Search the web using DuckDuckGo.

    Use this tool to find current information, news, prices, or any other
    information that might not be in your training data. After searching,
    you can use fetch_url to read specific pages.

    Args:
        query: The search query
        num_results: Number of results to return (default 5, max 10)

    Returns:
        JSON string with query and results array containing title, url, and snippet
    """
    num_results = min(max(1, num_results), 10)

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))

        if not results:
            return json.dumps({"query": query, "results": [], "error": "No results found"})

        search_results = [
            {
                "title": r.get("title", "No title"),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]

        return json.dumps({"query": query, "results": search_results})

    except Exception as e:
        return json.dumps({"query": query, "results": [], "error": str(e)})


# Valid aspect ratios for image generation
VALID_ASPECT_RATIOS = {"1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3"}


@tool
def generate_image(prompt: str, aspect_ratio: str = "1:1") -> str:
    """Generate an image using Gemini image generation.

    Use this tool when the user asks you to create, generate, draw, or make an image.
    You should craft a detailed, descriptive prompt that captures what the user wants.

    Args:
        prompt: A detailed description of the image to generate. Be specific about
                style, colors, composition, lighting, and any text to include.
        aspect_ratio: The image aspect ratio. Options: 1:1 (square, default),
                     16:9 (landscape/widescreen), 9:16 (portrait/mobile),
                     4:3 (standard), 3:4 (portrait), 3:2, 2:3

    Returns:
        JSON with the prompt used and base64 image data, or an error message
    """
    # Validate prompt
    if not prompt or not prompt.strip():
        return json.dumps({"error": "Prompt cannot be empty"})

    prompt = prompt.strip()
    if len(prompt) > Config.MAX_IMAGE_PROMPT_LENGTH:
        return json.dumps(
            {
                "error": f"Prompt is too long. Maximum length is {Config.MAX_IMAGE_PROMPT_LENGTH} characters, got {len(prompt)}"
            }
        )

    # Validate aspect ratio
    if aspect_ratio not in VALID_ASPECT_RATIOS:
        return json.dumps(
            {
                "error": f"Invalid aspect ratio '{aspect_ratio}'. Valid options: {', '.join(sorted(VALID_ASPECT_RATIOS))}"
            }
        )

    try:
        # Create client with API key
        client = genai.Client(api_key=Config.GEMINI_API_KEY)

        # Generate image using Gemini image generation model
        # The model generates one final image by default (uses internal "thinking" to iterate)
        response = client.models.generate_content(
            model=Config.IMAGE_GENERATION_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )

        # Extract image from response
        if not response.candidates:
            return json.dumps(
                {"error": "No image generated. The model may have refused the request."}
            )

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            return json.dumps(
                {"error": "No image generated. The model may have refused the request."}
            )

        for part in candidate.content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_data = part.inline_data
                # Encode to base64
                if image_data.data is None:
                    continue
                image_base64 = base64.b64encode(image_data.data).decode("utf-8")
                return json.dumps(
                    {
                        "prompt": prompt,
                        "aspect_ratio": aspect_ratio,
                        "image": {
                            "data": image_base64,
                            "mime_type": image_data.mime_type or "image/png",
                        },
                    }
                )

        return json.dumps({"error": "No image data found in response"})

    except Exception as e:
        error_msg = str(e)
        # Provide user-friendly error messages for common issues
        if "SAFETY" in error_msg.upper() or "BLOCKED" in error_msg.upper():
            return json.dumps(
                {
                    "error": "The image generation was blocked due to safety filters. Please try a different prompt."
                }
            )
        return json.dumps({"error": f"Image generation failed: {error_msg}"})


# List of all available tools for the agent
TOOLS = [fetch_url, web_search, generate_image]
