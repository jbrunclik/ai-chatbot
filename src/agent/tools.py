"""Web tools for the AI agent."""

import base64
import json
from typing import Any

import html2text
import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from google import genai
from google.genai import types
from langchain_core.tools import tool

from src.config import Config
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _extract_text_from_html(html: str, max_length: int | None = None) -> str:
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
    limit = max_length if max_length is not None else Config.HTML_TEXT_MAX_LENGTH
    if len(text) > limit:
        text = text[:limit] + "\n\n[Content truncated...]"

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
    logger.info("fetch_url called", extra={"url": url})
    if not url.startswith(("http://", "https://")):
        logger.warning("Invalid URL format", extra={"url": url})
        return json.dumps(
            {"error": f"Invalid URL '{url}'. URL must start with http:// or https://"}
        )

    try:
        logger.debug("Fetching URL", extra={"url": url})
        with httpx.Client(
            timeout=float(Config.TOOL_TIMEOUT),
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            },
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            logger.debug(
                "URL fetched successfully",
                extra={
                    "url": url,
                    "status_code": response.status_code,
                    "content_length": len(response.text),
                },
            )

            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                logger.warning(
                    "Non-text content type", extra={"url": url, "content_type": content_type}
                )
                return json.dumps({"error": f"URL returned non-text content type: {content_type}"})

            extracted_text = _extract_text_from_html(response.text)
            logger.info(
                "URL content extracted", extra={"url": url, "text_length": len(extracted_text)}
            )
            return extracted_text

    except httpx.TimeoutException:
        logger.warning("URL fetch timeout", extra={"url": url})
        return json.dumps({"error": f"Request to {url} timed out"})
    except httpx.HTTPStatusError as e:
        logger.warning(
            "URL fetch HTTP error", extra={"url": url, "status_code": e.response.status_code}
        )
        return json.dumps({"error": f"HTTP {e.response.status_code} when fetching {url}"})
    except httpx.RequestError as e:
        logger.error("URL fetch request error", extra={"url": url, "error": str(e)}, exc_info=True)
        return json.dumps({"error": f"Failed to fetch {url}: {e}"})


@tool
def web_search(query: str, num_results: int | None = None) -> str:
    """Search the web using DuckDuckGo.

    Use this tool to find current information, news, prices, or any other
    information that might not be in your training data. After searching,
    you can use fetch_url to read specific pages.

    Args:
        query: The search query
        num_results: Number of results to return (default from config, max from config)

    Returns:
        JSON string with query and results array containing title, url, and snippet
    """
    if num_results is None:
        num_results = Config.WEB_SEARCH_DEFAULT_RESULTS
    logger.info("web_search called", extra={"query": query, "num_results": num_results})
    num_results = min(max(1, num_results), Config.WEB_SEARCH_MAX_RESULTS)

    try:
        logger.debug("Executing DuckDuckGo search")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))

        if not results:
            logger.warning("No search results found", extra={"query": query})
            return json.dumps({"query": query, "results": [], "error": "No results found"})

        search_results = [
            {
                "title": r.get("title", "No title"),
                "url": r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in results
        ]

        logger.info("Search completed", extra={"query": query, "result_count": len(search_results)})
        return json.dumps({"query": query, "results": search_results})

    except Exception as e:
        logger.error("Search error", extra={"query": query, "error": str(e)}, exc_info=True)
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
        logger.debug(
            "Starting image generation",
            extra={"model": Config.IMAGE_GENERATION_MODEL, "aspect_ratio": aspect_ratio},
        )
        # Create client with API key
        client = genai.Client(api_key=Config.GEMINI_API_KEY)

        # Generate image using Gemini image generation model
        # The model generates one final image by default (uses internal "thinking" to iterate)
        logger.debug("Calling Gemini image generation API")
        response = client.models.generate_content(
            model=Config.IMAGE_GENERATION_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
            ),
        )
        logger.debug("Image generation API call completed")

        # Extract usage metadata for cost tracking
        usage_metadata_dict: dict[str, Any] | None = None
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            usage_metadata_dict = {
                "prompt_token_count": getattr(usage, "prompt_token_count", 0) or 0,
                "candidates_token_count": getattr(usage, "candidates_token_count", 0) or 0,
                "thoughts_token_count": getattr(usage, "thoughts_token_count", 0) or 0,
                "total_token_count": getattr(usage, "total_token_count", 0) or 0,
            }
            logger.debug(
                "Image generation usage metadata extracted",
                extra=usage_metadata_dict,
            )

        # Extract image from response
        if not response.candidates:
            logger.warning("No candidates in image generation response")
            return json.dumps(
                {"error": "No image generated. The model may have refused the request."}
            )

        candidate = response.candidates[0]
        if not candidate.content or not candidate.content.parts:
            logger.warning("No content/parts in image generation response")
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
                image_size = len(image_data.data)
                logger.info(
                    "Image generated successfully",
                    extra={
                        "image_size_bytes": image_size,
                        "mime_type": image_data.mime_type,
                        "aspect_ratio": aspect_ratio,
                    },
                )
                # Return TWO things:
                # 1. A summary for the LLM (no image data - to avoid sending 500KB back to the model)
                # 2. The full image data stored in a special field that gets extracted server-side
                #
                # The LLM only sees the summary, which confirms the image was generated.
                # The server extracts _full_result for storage and display.
                result = {
                    "success": True,
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio,
                    "message": "Image generated successfully. The image will be displayed to the user.",
                    # This field is extracted server-side and NOT sent to the LLM
                    "_full_result": {
                        "image": {
                            "data": image_base64,
                            "mime_type": image_data.mime_type or "image/png",
                        },
                    },
                }
                # Include usage_metadata for cost tracking
                if usage_metadata_dict:
                    result["usage_metadata"] = usage_metadata_dict

                return json.dumps(result)

        logger.warning("No image data found in response parts")
        return json.dumps({"error": "No image data found in response"})

    except Exception as e:
        error_msg = str(e)
        logger.error("Image generation exception", extra={"error": error_msg}, exc_info=True)
        # Provide user-friendly error messages for common issues
        if "SAFETY" in error_msg.upper() or "BLOCKED" in error_msg.upper():
            logger.warning("Image generation blocked by safety filters")
            return json.dumps(
                {
                    "error": "The image generation was blocked due to safety filters. Please try a different prompt."
                }
            )
        return json.dumps({"error": f"Image generation failed: {error_msg}"})


# List of all available tools for the agent
TOOLS = [fetch_url, web_search, generate_image]
