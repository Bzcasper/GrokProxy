"""
Grok Web Client for Vercel Deployment.
Proxies requests to the Grok web interface (grok.com).
"""

import httpx
import json
from typing import Dict, Any, Optional, AsyncIterator, List
import time


class GrokClient:
    """Client for Grok Web Interface interactions."""
    
    GROK_URL = "https://grok.com/rest/app-chat/conversations/new"
    
    def __init__(self, session_cookies: Dict[str, str], user_agent: Optional[str] = None):
        """
        Initialize Grok client with session cookies.
        
        Args:
            session_cookies: Dictionary of cookies for authentication
            user_agent: User agent string to mimic browser
        """
        self.cookies = session_cookies
        self.user_agent = user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        self.headers = {
            "authority": "grok.com",
            "accept": "*/*",
            "content-type": "application/json",
            "origin": "https://grok.com",
            "referer": "https://grok.com/?referrer=website",
            "user-agent": self.user_agent
        }
        
        # Initialize client with cookies and headers
        self.client = httpx.AsyncClient(
            cookies=self.cookies,
            headers=self.headers,
            timeout=httpx.Timeout(240.0, connect=60.0),
            follow_redirects=True
        )
    
    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format list of messages into a single prompt string."""
        # Simple concatenation for now, as the web interface "new conversation" 
        # typically expects a starting prompt.
        # We could improve this to handle conversation history better if needed.
        formatted_prompt = ""
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                formatted_prompt += f"System: {content}\n\n"
            elif role == "user":
                formatted_prompt += f"User: {content}\n\n"
            elif role == "assistant":
                formatted_prompt += f"Assistant: {content}\n\n"
        
        return formatted_prompt.strip()

    async def chat_completion(
        self,
        messages: list,
        model: str = "grok-3",
        temperature: float = 1.0,
        max_tokens: Optional[int] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Send chat completion request to Grok Web Interface.
        """
        if stream:
            raise ValueError("Use chat_completion_stream for streaming")
            
        prompt = self._format_messages(messages)
        payload = {"message": prompt, "modelName": model}
        
        full_response_text = ""
        
        try:
            async with self.client.stream("POST", self.GROK_URL, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    raise Exception(f"Grok Web API error: {response.status_code} - {error_text.decode('utf-8', errors='ignore')}")
                
                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            token = data.get("result", {}).get("response", {}).get("token")
                            if token:
                                full_response_text += token
                        except json.JSONDecodeError:
                            continue
                            
            return {
                "id": f"grok-{int(time.time())}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": full_response_text
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": len(prompt) // 4,
                    "completion_tokens": len(full_response_text) // 4,
                    "total_tokens": (len(prompt) + len(full_response_text)) // 4
                }
            }
            
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
        Stream chat completion from Grok Web Interface.
        """
        prompt = self._format_messages(messages)
        payload = {"message": prompt, "modelName": model}
        
        try:
            async with self.client.stream("POST", self.GROK_URL, json=payload) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    yield json.dumps({
                        "error": {
                            "message": f"Grok Web API error: {response.status_code} - {error_text.decode('utf-8', errors='ignore')}",
                            "type": "api_error"
                        }
                    })
                    return

                async for line in response.aiter_lines():
                    if line:
                        try:
                            data = json.loads(line)
                            token = data.get("result", {}).get("response", {}).get("token")
                            if token:
                                # Format as OpenAI-compatible SSE
                                chunk = {
                                    "id": f"grok-{int(time.time())}",
                                    "object": "chat.completion.chunk",
                                    "created": int(time.time()),
                                    "model": model,
                                    "choices": [
                                        {
                                            "index": 0,
                                            "delta": {"content": token},
                                            "finish_reason": None
                                        }
                                    ]
                                }
                                yield json.dumps(chunk)
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            yield json.dumps({
                "error": {
                    "message": f"Stream failed: {str(e)}",
                    "type": "stream_error"
                }
            })

    async def generate_image(
        self,
        prompt: str,
        model: str = "grok-3"
    ) -> Dict[str, Any]:
        """
        Generate image using Grok Web Interface.
        """
        # Image generation via web interface usually involves sending a prompt 
        # and parsing the response for image URLs.
        # This is complex and might vary. For now, we'll try sending the prompt.
        messages = [{"role": "user", "content": f"Generate an image: {prompt}"}]
        return await self.chat_completion(messages, model=model)

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
