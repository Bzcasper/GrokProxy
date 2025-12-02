import json
import logging
import asyncio
import time
from typing import AsyncGenerator, Optional

import httpx

from modules.api import start_grok_conversation
from changecookie import ChangeCookie
from utils import get_default_user_agent

# Configure logging
logger = logging.getLogger(__name__)


class GrokClient:
    """Async Grok client with cookie rotation and retry logic."""
    
    def __init__(self, cookie: Optional[str] = None, user_agent: Optional[str] = None, 
                 cookie_manager: Optional[ChangeCookie] = None):
        """
        Initialize the Grok client.
        
        Args:
            cookie: Initial cookie string (optional if using cookie_manager)
            user_agent: User agent string (defaults to Safari 18.3)
            cookie_manager: ChangeCookie instance for rotation (optional)
        """
        self.cookie_manager = cookie_manager
        self.cookie = cookie if cookie else (cookie_manager.get_cookie() if cookie_manager else "")
        self.user_agent = user_agent if user_agent else get_default_user_agent()
        
        # Session data for continuity
        self.session_data = None
        
        # Retry configuration
        self.max_retries = 5
        self.retry_delays = [2, 5, 10, 20, 30]
        
        # Rate limiting
        self.last_request_time = 0
        self.rate_limit_delay = 1.0
        
        logger.info("GrokClient initialized")
    
    def rotate_credentials(self) -> None:
        """Rotate to the next cookie and user agent if cookie manager is available."""
        if self.cookie_manager:
            self.cookie = self.cookie_manager.get_cookie()
            self.user_agent = self.cookie_manager.get_user_agent()
            # Clear session data on rotation to force new session
            self.session_data = None
            logger.info("Credentials rotated to next cookie")
        else:
            logger.warning("No cookie manager available for rotation")
    
    async def _apply_rate_limit(self) -> None:
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    async def chat(self, prompt: str, model: str, reasoning: bool = False) -> AsyncGenerator[str, None]:
        """
        Send a chat request to Grok API and stream the response.
        """
        await self._apply_rate_limit()
        
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # Run the synchronous start_grok_conversation in a thread to avoid blocking
                # For now, we'll run it directly as it uses curl_cffi which is sync
                # Ideally this should be run_in_executor
                
                logger.info(f"Sending request to Grok API (attempt {retry_count + 1}/{self.max_retries})")
                
                # If we have cookies from rotation, we should pass them?
                # The start_grok_conversation creates its own session.
                # We might need to inject cookies if we want to use the rotated ones.
                # However, the provided code generates new keys and session.
                # It seems to rely on 'load_session' to get cookies from grok.com/c
                # But if we have premium cookies, we might need to inject them.
                # The provided code has 'load_existing' which takes session_data.
                # Let's assume for now we start fresh or continue existing session.
                
                # Note: The provided `start_grok_conversation` handles retries for anti-bot internally recursively.
                # But we have our own retry loop here.
                
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: start_grok_conversation(prompt, session_data=self.session_data)
                )
                
                if "error" in result:
                    error_msg = result["error"]
                    logger.error(f"API error: {error_msg}")
                    
                    error_str = str(error_msg)
                    if "anti-bot" in error_str or "403" in error_str or "Too many requests" in error_str or '"code":8' in error_str:
                        logger.warning("Rate limit or auth error detected, rotating credentials...")
                        self.rotate_credentials()
                        retry_count += 1
                        await asyncio.sleep(self.retry_delays[min(retry_count, len(self.retry_delays)-1)])
                        continue
                        
                    yield f"Error: {error_msg}"
                    return

                # Success
                self.session_data = result.get("extra_data")
                
                # Stream response
                stream_data = result.get("stream_response", [])
                for token in stream_data:
                    yield token
                
                # Yield images if any
                images = result.get("images", [])
                if images:
                    yield "\n\nGenerated Images:\n"
                    for img in images:
                        # Assuming img has 'url' or similar. Let's dump it or format it.
                        # Grok image objects usually have 'imageUrl' or 'id'.
                        # Let's try to construct a proxy URL if we can, or just the direct URL.
                        # For now, let's yield the raw markdown image.
                        if 'imageUrl' in img:
                            yield f"![Generated Image]({img['imageUrl']})\n"
                        elif 'id' in img:
                            # If we have an ID, maybe we can construct a URL?
                            # For now just print what we have to be safe
                            yield f"\n[Image Attachment: {img.get('id')}]"
                
                return

            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                retry_count += 1
                await asyncio.sleep(self.retry_delays[min(retry_count, len(self.retry_delays)-1)])
        
        yield "Error: Maximum retry attempts exceeded"

    async def download_image(self, url: str) -> AsyncGenerator[bytes, None]:
        """Download an image using the authenticated session."""
        # This needs to be implemented using the session from start_grok_conversation
        # But start_grok_conversation doesn't expose the session object directly in return
        # It returns extra_data with cookies.
        # We can create a new requests session with those cookies.
        try:
            async with httpx.AsyncClient() as client:
                headers = {"User-Agent": self.user_agent}
                if self.session_data and "cookies" in self.session_data:
                    client.cookies.update(self.session_data["cookies"])
                
                async with client.stream("GET", url, headers=headers) as response:
                    if response.status_code == 200:
                        async for chunk in response.aiter_bytes():
                            yield chunk
                    else:
                        logger.error(f"Failed to download image: {response.status_code}")
                        yield b""
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            yield b""

    async def close(self) -> None:
        """Close the client."""
        logger.info("GrokClient closed")
