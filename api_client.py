"""
api_client.py - OpenAI API client with async support and retry logic
Handles API calls with exponential backoff, token counting, and cost estimation
"""

import asyncio
import aiohttp
import json
import time
from typing import Dict, Any, Optional, Tuple
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
                    # Get response ID from headers
                    request_id = resp.headers.get("openai-organization", "unknown")
                    
                    if resp.status == 200:
                        data = await resp.json()
                        
                        try:
                            # Extract response
                            content = data["choices"][0]["message"]["content"]
                            json_data = json.loads(content)
                            
                            # Extract token counts
                            input_tokens = data["usage"]["prompt_tokens"]
                            output_tokens = data["usage"]["completion_tokens"]
                            
                            return APIResponse(
                                success=True,
                                data=json_data,
                                input_tokens=input_tokens,
                                output_tokens=output_tokens,
                                request_id=request_id
                            )
                        
                        except json.JSONDecodeError as e:
                            return APIResponse(
                                success=False,
                                error=f"Invalid JSON in response: {e}",
                                error_type="invalid_json",
                                request_id=request_id
                            )
                        
                        except (KeyError, IndexError) as e:
                            return APIResponse(
                                success=False,
                                error=f"Unexpected response format: {e}",
                                error_type="invalid_json",
                                request_id=request_id
                            )
                    
                    elif resp.status == 429:
                        # Rate limited
                        return APIResponse(
                            success=False,
                            error="Rate limited (429)",
                            error_type="rate_limit",
                            request_id=request_id
                        )
                    
                    elif resp.status in [408, 504]:
                        # Timeout
                        return APIResponse(
                            success=False,
                            error=f"Timeout ({resp.status})",
                            error_type="timeout",
                            request_id=request_id
                        )
                    
                    elif resp.status == 400:
                        # Bad request - don't retry
                        error_data = await resp.json()
                        error_msg = error_data.get("error", {}).get("message", "Unknown error")
                        return APIResponse(
                            success=False,
                            error=f"Bad request (400): {error_msg}",
                            error_type="bad_request",
                            request_id=request_id
                        )
                    
                    elif resp.status == 401:
                        # Authentication error
                        return APIResponse(
                            success=False,
                            error="Authentication failed (401)",
                            error_type="auth_error",
                            request_id=request_id
                        )
                    
                    else:
                        error_data = await resp.text()
                        return APIResponse(
                            success=False,
                            error=f"HTTP {resp.status}: {error_data[:200]}",
                            error_type="http_error",
                            request_id=request_id
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
