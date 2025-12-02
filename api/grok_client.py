"""
Grok API client for chat completions and image generation.
"""

import httpx
import json
from typing import Dict, Any, Optional, AsyncIterator
import time


class GrokClient:
    """Client for Grok API interactions."""
    
    BASE_URL = "https://api.x.ai"
    
    def __init__(self, session_cookies: Dict[str, str]):
        """
        Initialize Grok client with session cookies.
        
        Args:
            session_cookies: Dictionary of cookies for authentication
        """
        self.cookies = session_cookies
        self.client = httpx.AsyncClient(
            cookies=self.cookies,
            timeout=60.0,
            follow_redirects=True
        )
    
    async def chat_completion(
        self,
        messages: list,
        model: str = "grok-3",
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Send chat completion request to Grok API.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            
        Returns:
            API response dict
        """
        url = f"{self.BASE_URL}/v1/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": stream
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            raise Exception(f"Grok API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise Exception(f"Request failed: {str(e)}")
    
    async def chat_completion_stream(
        self,
        messages: list,
        model: str = "grok-3",
        temperature: float = 1.0,
        max_tokens: Optional[int] = None
    ) -> AsyncIterator[str]:
        """
        Stream chat completion from Grok API.
        
        Yields:
            Server-sent event data chunks
        """
        url = f"{self.BASE_URL}/v1/chat/completions"
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "stream": True
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        try:
            async with self.client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]  # Remove "data: " prefix
                        if data.strip() == "[DONE]":
                            break
                        yield data
        except httpx.HTTPStatusError as e:
            raise Exception(f"Grok API error: {e.response.status_code}")
        except Exception as e:
            raise Exception(f"Stream failed: {str(e)}")
    
    async def generate_image(
        self,
        prompt: str,
        model: str = "grok-3"
    ) -> Dict[str, Any]:
        """
        Generate image using Grok API.
        
        Args:
            prompt: Image generation prompt
            model: Model to use
            
        Returns:
            API response with image URL
        """
        # Grok uses chat completions for image generation
        # The response will contain image URLs
        messages = [
            {
                "role": "user",
                "content": f"Generate an image: {prompt}"
            }
        ]
        
        return await self.chat_completion(messages, model=model)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
