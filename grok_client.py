"""Modern httpx-based Grok client with cookie rotation support."""

import json
import logging
import asyncio
import time
from typing import AsyncGenerator, Optional

import httpx

from configs import CHAT_URL
from utils import get_default_chat_payload, get_default_user_agent
from changecookie import ChangeCookie

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
        self.client = httpx.AsyncClient(timeout=240.0)
        
        # Retry configuration
        self.max_retries = 5
        self.retry_delays = [2, 5, 10, 20, 30]
        
        # Rate limiting
        self.last_request_time = 0
        self.rate_limit_delay = 1.0
        
        logger.info("GrokClient initialized with httpx")
    
    @property
    def headers(self):
        """Generate request headers."""
        return {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "en-US,en;q=0.9",
            "Content-Type": "application/json",
            "Cookie": self.cookie,
            "Origin": "https://grok.com",
            "Referer": "https://grok.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": self.user_agent,
            "x-statsig-id": "eh4JV3lADQrJ0SwPwQOK6oPwVFwLnhl7c5lviHSdJVRhyfDgT9nvto2ritghwnyDF20ipH76JDpnj2sO1IYmwagqwvW/eQ",
        }
    
    def rotate_credentials(self) -> None:
        """Rotate to the next cookie and user agent if cookie manager is available."""
        if self.cookie_manager:
            self.cookie = self.cookie_manager.get_cookie()
            self.user_agent = self.cookie_manager.get_user_agent()
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
        
        Args:
            prompt: The user's message
            model: Model name (e.g., 'grok-3', 'grok-latest')
            reasoning: Whether to enable reasoning mode
            
        Yields:
            Response tokens from the streaming API
        """
        await self._apply_rate_limit()
        
        # Build payload
        default_payload = get_default_chat_payload()
        update_payload = {
            "modelName": model,
            "message": prompt,
            "isReasoning": reasoning,
        }
        default_payload.update(update_payload)
        payload = default_payload
        
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                logger.info(f"Sending request to Grok API (attempt {retry_count + 1}/{self.max_retries})")
                logger.debug(f"Model: {model}, Reasoning: {reasoning}")
                
                async with self.client.stream(
                    method="POST",
                    url=CHAT_URL,
                    headers=self.headers,
                    json=payload,
                ) as response:
                    if response.status_code == 200:
                        logger.info("✓ Connection established (200 OK)")
                        async for chunk in response.aiter_lines():
                            if chunk:
                                try:
                                    chunk_json = json.loads(chunk)
                                    
                                    # Check for errors
                                    if "error" in chunk_json:
                                        error_msg = chunk_json.get("error", {}).get("message", "Unknown error")
                                        logger.error(f"API error: {error_msg}")
                                        raise RuntimeError(error_msg)
                                    
                                    # Extract response token
                                    token = chunk_json.get("result", {}).get("response", {}).get("token", "")
                                    
                                    # Extract generated images
                                    response_data = chunk_json.get("result", {}).get("response", {})
                                    generated_images = response_data.get("generatedImageUrls", [])
                                    
                                    # Also check inside modelResponse
                                    if not generated_images:
                                        model_response = response_data.get("modelResponse", {})
                                        generated_images = model_response.get("generatedImageUrls", [])
                                    
                                    if generated_images:
                                        for img_path in generated_images:
                                            # Construct full URL (assuming assets.grok.com)
                                            full_url = f"https://assets.grok.com/{img_path}"
                                            # Yield as markdown image
                                            yield f"\n\n![Generated Image]({full_url})\n"
                                    
                                    if token:
                                        yield token
                                        
                                except json.JSONDecodeError:
                                    logger.debug(f"Skipping non-JSON chunk: {chunk[:100]}")
                                    pass
                        
                        logger.info("Stream finished successfully")
                        return  # Success, exit retry loop
                    
                    elif response.status_code == 429:
                        # Rate limit
                        delay = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                        logger.warning(f"Rate limit hit (429), waiting {delay}s before retry...")
                        await asyncio.sleep(delay)
                        self.rotate_credentials()
                        retry_count += 1
                        continue
                    
                    elif response.status_code in [401, 403]:
                        # Authentication failed
                        delay = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                        error_body = await response.aread()
                        error_text = error_body.decode()[:500]
                        
                        logger.error(f"Authentication failed ({response.status_code})")
                        logger.info(f"Error body: {error_text}")
                        
                        if "anti-bot" in error_text.lower() or "cloudflare" in error_text.lower():
                            logger.error("Request rejected by anti-bot rules. Cookies may be expired.")
                        
                        logger.info(f"Rotating credentials and waiting {delay}s...")
                        await asyncio.sleep(delay)
                        self.rotate_credentials()
                        retry_count += 1
                        continue
                    
                    elif response.status_code == 503:
                        # Service unavailable
                        delay = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                        logger.warning(f"Service unavailable (503), waiting {delay}s before retry...")
                        await asyncio.sleep(delay)
                        self.rotate_credentials()
                        retry_count += 1
                        continue
                    
                    else:
                        # Other errors
                        error_body = await response.aread()
                        error_text = error_body.decode()[:200]
                        logger.error(f"Request failed: {response.status_code} - {error_text}")
                        yield f"Error: {response.status_code}"
                        return
            
            except httpx.TimeoutException:
                logger.error("Request timeout!")
                retry_count += 1
                if retry_count >= self.max_retries:
                    yield "Error: Request timeout after retries"
                    return
                await asyncio.sleep(1)
            
            except httpx.RequestError as e:
                logger.error(f"Request error: {str(e)}")
                retry_count += 1
                if retry_count >= self.max_retries:
                    yield f"Error: Request failed after {self.max_retries} retries"
                    return
                await asyncio.sleep(1)
            
            except RuntimeError as e:
                # API returned an error
                logger.error(f"API error: {str(e)}")
                yield f"Error: {str(e)}"
                return
            
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}", exc_info=True)
                retry_count += 1
                if retry_count >= self.max_retries:
                    yield f"Error: Unexpected error after {self.max_retries} retries"
                    return
                await asyncio.sleep(1)
        
        logger.error(f"Max retries ({self.max_retries}) exceeded")
        yield "Error: Maximum retry attempts exceeded"
    
    async def download_image(self, url: str) -> AsyncGenerator[bytes, None]:
        """
        Download an image using the authenticated session.
        
        Args:
            url: The image URL to download
            
        Yields:
            Image bytes chunks
        """
        await self._apply_rate_limit()
        
        try:
            logger.info(f"Downloading image from: {url}")
            
            # Determine headers based on domain
            if "grok.com" in url or "x.ai" in url:
                # Internal Grok URL - keep all headers
                headers = self.headers
            else:
                # External URL (Azure/AWS/etc) - use minimal headers
                # Extra headers like Content-Type or Cookie can cause 403s with signed URLs
                headers = {
                    "User-Agent": self.user_agent,
                    "Accept": "*/*"
                }
                logger.info("External domain detected - using minimal headers")
            
            async with self.client.stream("GET", url, headers=headers) as response:
                if response.status_code == 200:
                    async for chunk in response.aiter_bytes():
                        yield chunk
                else:
                    logger.error(f"Failed to download image: {response.status_code}")
                    # Log response body for debugging
                    error_body = await response.aread()
                    logger.error(f"Error body: {error_body.decode()[:200]}")
                    yield b""
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            yield b""

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("GrokClient closed")
