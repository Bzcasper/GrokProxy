"""
Proxy mode for Vercel deployment.
Forwards all requests to the local ngrok instance.
"""

import os
import httpx
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse


class ProxyClient:
    """Client for forwarding requests to local ngrok instance."""
    
    def __init__(self, ngrok_url: Optional[str] = None):
        self.ngrok_url = ngrok_url or os.getenv("NGROK_PROXY_URL")
        if not self.ngrok_url:
            raise ValueError("NGROK_PROXY_URL environment variable not set")
        
        # Remove trailing slash
        self.ngrok_url = self.ngrok_url.rstrip('/')
        
        # Create HTTP client with reasonable timeouts
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(120.0, connect=10.0),
            follow_redirects=True
        )
    
    async def forward_request(
        self,
        request: Request,
        path: str
    ) -> StreamingResponse | JSONResponse:
        """
        Forward a request to the ngrok instance.
        
        Args:
            request: The incoming FastAPI request
            path: The path to forward to (e.g., "/v1/chat/completions")
        
        Returns:
            StreamingResponse or JSONResponse with the proxied response
        """
        # Build target URL
        target_url = f"{self.ngrok_url}{path}"
        
        # Get request body
        body = await request.body()
        
        # Copy headers, excluding host and other problematic headers
        headers = dict(request.headers)
        headers_to_remove = ['host', 'content-length', 'transfer-encoding']
        for header in headers_to_remove:
            headers.pop(header, None)
        
        try:
            # Forward the request
            response = await self.client.request(
                method=request.method,
                url=target_url,
                content=body,
                headers=headers,
                params=request.query_params
            )
            
            # Check if response is streaming (Server-Sent Events)
            content_type = response.headers.get('content-type', '')
            if 'text/event-stream' in content_type or 'stream' in content_type.lower():
                # Stream the response
                async def stream_generator():
                    async for chunk in response.aiter_bytes():
                        yield chunk
                
                return StreamingResponse(
                    stream_generator(),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=content_type
                )
            else:
                # Return non-streaming response
                return JSONResponse(
                    content=response.json() if response.headers.get('content-type', '').startswith('application/json') else {"data": response.text},
                    status_code=response.status_code,
                    headers=dict(response.headers)
                )
        
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail="Gateway timeout: Local ngrok instance did not respond in time"
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=502,
                detail=f"Bad gateway: Could not connect to ngrok instance at {self.ngrok_url}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=502,
                detail=f"Proxy error: {str(e)}"
            )
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Global proxy client instance
_proxy_client: Optional[ProxyClient] = None


def get_proxy_client() -> ProxyClient:
    """Get or create the global proxy client."""
    global _proxy_client
    if _proxy_client is None:
        _proxy_client = ProxyClient()
    return _proxy_client


async def is_proxy_mode_enabled() -> bool:
    """Check if proxy mode is enabled."""
    proxy_mode = os.getenv("PROXY_MODE", "false").lower()
    ngrok_url = os.getenv("NGROK_PROXY_URL")
    
    # Proxy mode is enabled if:
    # 1. PROXY_MODE is explicitly set to true, OR
    # 2. NGROK_PROXY_URL is set and DATABASE_URL is not set
    if proxy_mode in ["true", "1", "yes", "on"]:
        return True
    
    if ngrok_url and not os.getenv("DATABASE_URL"):
        return True
    
    return False
