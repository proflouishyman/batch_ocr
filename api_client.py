"""
api_client.py - OpenAI API client with async support and retry logic
Handles API calls with exponential backoff, token counting, and cost estimation
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, Optional, Tuple
from collections.abc import Iterable
from dataclasses import dataclass
import base64


@dataclass
class APIResponse:
    """Container for API response data"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    error_type: Optional[str] = None  # "rate_limit", "timeout", "invalid_json", "unknown"
    input_tokens: int = 0
    output_tokens: int = 0
    request_id: Optional[str] = None
    raw_response: Optional[str] = None


class OpenAIClient:
    """Async OpenAI API client with retry logic"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: int = 60,
        max_retries: int = 3,
        backoff_multiplier: float = 2.0,
        logger=None
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_multiplier = backoff_multiplier
        self.logger = logger

        # Session will be created per request (for async context management)

    @staticmethod
    def _parse_assistant_message(message: Dict[str, Any]) -> Dict[str, Any]:
        """Extract the JSON payload from an assistant message."""
        if "content" not in message:
            raise KeyError("message.content missing")

        content = message["content"]

        if isinstance(content, str):
            stripped = content.strip()
            if not stripped:
                raise json.JSONDecodeError("empty content", stripped, 0)
            return json.loads(stripped)

        if isinstance(content, Iterable):
            json_block = None
            text_segments = []
            for block in content:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type in {"output_json", "json"} and "json" in block:
                    json_block = block["json"]
                    break
                if block_type in {"text", "output_text"} and "text" in block:
                    text_segments.append(str(block["text"]))

            if json_block is not None:
                if isinstance(json_block, (dict, list)):
                    return json_block
                if isinstance(json_block, str):
                    stripped = json_block.strip()
                    if not stripped:
                        raise json.JSONDecodeError("empty output_json payload", stripped, 0)
                    return json.loads(stripped)
                raise TypeError(
                    f"Unsupported output_json payload type: {type(json_block).__name__}"
                )

            joined = "".join(text_segments).strip()
            if not joined:
                raise json.JSONDecodeError("no textual content", joined, 0)
            return json.loads(joined)

        raise TypeError(f"Unsupported content type: {type(content).__name__}")

    @staticmethod
    def _content_preview(data: Dict[str, Any]) -> str:
        """Return a short preview of the assistant content for diagnostics."""
        try:
            content = data["choices"][0]["message"].get("content", "")
        except Exception:
            return "<unavailable>"

        if isinstance(content, str):
            preview_src = content
        elif isinstance(content, Iterable):
            snippets = []
            for block in content:
                if isinstance(block, dict):
                    if "text" in block:
                        snippets.append(str(block["text"]))
                    elif "json" in block:
                        snippets.append(json.dumps(block["json"], ensure_ascii=False))
            preview_src = " | ".join(snippets)
        else:
            preview_src = str(content)

        preview = preview_src.strip().replace("\n", " ")
        if len(preview) > 200:
            preview = preview[:200] + "…"
        return preview or "<empty>"

    async def process_image(
        self,
        image_base64: str,
        system_prompt: str,
        user_prompt_template: str
    ) -> APIResponse:
        """
        Process a single image through GPT-5 API
        
        Args:
            image_base64: Base64-encoded image data
            system_prompt: System message
            user_prompt_template: User message template
        
        Returns:
            APIResponse with result or error
        """
        attempt = 0
        last_error = None
        
        while attempt < self.max_retries:
            try:
                if attempt > 0:
                    # Exponential backoff
                    wait_time = (self.backoff_multiplier ** (attempt - 1))
                    if self.logger:
                        self.logger.debug(f"Retry attempt {attempt}: waiting {wait_time}s")
                    await asyncio.sleep(wait_time)
                
                # Make API call
                response = await self._make_api_call(
                    image_base64, system_prompt, user_prompt_template
                )
                
                if response.success:
                    return response
                
                # Check if error is retryable
                if response.error_type in ["rate_limit", "timeout"]:
                    attempt += 1
                    last_error = response
                    continue
                else:
                    # Non-retryable error
                    return response
            
            except Exception as e:
                attempt += 1
                last_error = APIResponse(
                    success=False,
                    error=str(e),
                    error_type="unknown"
                )
                
                if attempt >= self.max_retries:
                    if self.logger:
                        self.logger.error(f"Max retries exceeded: {e}")
                    return last_error
        
        # If we got here, we exhausted retries
        return last_error or APIResponse(
            success=False,
            error="Max retries exceeded",
            error_type="unknown"
        )
    
    async def _make_api_call(
        self,
        image_base64: str,
        system_prompt: str,
        user_prompt_template: str
    ) -> APIResponse:
        """Make single API call to OpenAI"""
        
        # Construct message with image
        messages = [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": user_prompt_template
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high"
                        }
                    }
                ]
            }
        ]
        
        payload = {
            "model": self.model,
            "messages": messages,
            #"temperature": 0.2,  # Lower temp for consistency
            "max_completion_tokens": 2048,
            "response_format": {
                "type": "json_object"
            }
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as resp:
                    # Capture the server-provided request identifier if available.
                    # According to OpenAI's public API documentation, the primary
                    # header is `x-request-id`, with `openai-request-id` used on
                    # some legacy gateways.  Fall back to a sentinel so downstream
                    # logging always has a value.
                    request_id = (
                        resp.headers.get("x-request-id")
                        or resp.headers.get("openai-request-id")
                        or resp.headers.get("request-id")
                        or "unknown"
                    )
                    response_text = await resp.text()

                    if resp.status == 200:
                        try:
                            data = json.loads(response_text)
                        except json.JSONDecodeError as e:
                            return APIResponse(
                                success=False,
                                error=f"Invalid JSON in response body: {e}",
                                error_type="invalid_json",
                                request_id=request_id,
                                raw_response=response_text
                            )

                        try:
                            # Extract response content (supports both legacy string
                            # responses and the newer block-based payloads).
                            message = data["choices"][0]["message"]
                            json_data = self._parse_assistant_message(message)

                            # Extract token counts
                            usage = data.get("usage", {})
                            input_tokens = usage.get("prompt_tokens", 0)
                            output_tokens = usage.get("completion_tokens", 0)

                            # Prefer the response payload ID when available so it
                            # matches the identifier shown in the API dashboard.
                            request_id = data.get("id", request_id)

                            return APIResponse(
                                success=True,
                                data=json_data,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                request_id=request_id
                            )

                        except json.JSONDecodeError as e:
                            preview = self._content_preview(data)
                            return APIResponse(
                                success=False,
                                error=f"Invalid JSON in response: {e}. Content preview: {preview}",
                                error_type="invalid_json",
                                request_id=request_id,
                                raw_response=response_text
                            )

                        except (KeyError, IndexError, TypeError, ValueError) as e:
                            preview = self._content_preview(data)
                            return APIResponse(
                                success=False,
                                error=f"Unexpected response format: {e}. Content preview: {preview}",
                                error_type="invalid_json",
                                request_id=request_id,
                                raw_response=response_text
                            )

                    elif resp.status == 429:
                        # Rate limited
                        return APIResponse(
                            success=False,
                            error="Rate limited (429)",
                            error_type="rate_limit",
                            request_id=request_id,
                            raw_response=response_text
                        )

                    elif resp.status in [408, 504]:
                        # Timeout
                        return APIResponse(
                            success=False,
                            error=f"Timeout ({resp.status})",
                            error_type="timeout",
                            request_id=request_id,
                            raw_response=response_text
                        )

                    elif resp.status == 400:
                        # Bad request - don't retry
                        try:
                            error_data = json.loads(response_text)
                            error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        except json.JSONDecodeError:
                            error_msg = response_text[:200] if response_text else "Unknown error"
                        return APIResponse(
                            success=False,
                            error=f"Bad request (400): {error_msg}",
                            error_type="bad_request",
                            request_id=request_id,
                            raw_response=response_text
                        )

                    elif resp.status == 401:
                        # Authentication error
                        return APIResponse(
                            success=False,
                            error="Authentication failed (401)",
                            error_type="auth_error",
                            request_id=request_id,
                            raw_response=response_text
                        )

                    else:
                        return APIResponse(
                            success=False,
                            error=f"HTTP {resp.status}: {response_text[:200]}",
                            error_type="http_error",
                            request_id=request_id,
                            raw_response=response_text
                        )
        
        except asyncio.TimeoutError:
            return APIResponse(
                success=False,
                error="Request timeout",
                error_type="timeout"
            )
        
        except aiohttp.ClientError as e:
            return APIResponse(
                success=False,
                error=f"Client error: {e}",
                error_type="network_error"
            )
        
        except Exception as e:
            return APIResponse(
                success=False,
                error=f"Unexpected error: {e}",
                error_type="unknown"
            )
    
    def estimate_cost(self, input_tokens: int, output_tokens: int, 
                     input_cost_per_1k: float, output_cost_per_1k: float) -> float:
        """Estimate cost for a request"""
        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        return input_cost + output_cost


def encode_image_to_base64(image_path: str) -> str:
    """
    Encode image file to base64 string
    
    Args:
        image_path: Path to image file
    
    Returns:
        Base64-encoded image string
    """
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")
