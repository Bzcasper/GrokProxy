import json
import logging
import asyncio
import time
import uuid
import secrets
import base64
from typing import AsyncGenerator, Optional
from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError

from changecookie import ChangeCookie

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("grok")


class GrokRequest:
    """Handles requests to Grok AI API with Cloudflare bypass and automatic cookie rotation."""
    
    grok_url: str = "https://grok.com/rest/app-chat/conversations/new"

    # Cloudflare bypass headers (Chrome 130+)
    cloudflare_headers = {
        "accept": "*/*",
        "accept-encoding": "gzip, deflate, br",
        "accept-language": "en-US,en;q=0.9",
        "sec-ch-ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    }

    def __init__(self, proxy: Optional[str] = None):
        """
        Initialize the Grok request handler with Cloudflare bypass.
        
        Args:
            proxy: Optional proxy URL (e.g., "http://user:pass@proxy.com:port")
        """
        self.change_cookie = ChangeCookie()
        self.max_retries = 5
        self.retry_delays = [2, 5, 10, 20, 30]  # Progressive backoff
        
        # Rate limiting
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # Seconds between requests
        
        # Initialize curl_cffi session with Chrome impersonation
        self.proxy = proxy
        if proxy:
            logger.info(f"Using proxy: {proxy.split('@')[-1] if '@' in proxy else proxy}")
        self.session = AsyncSession(
            impersonate="chrome124", # Using chrome124 as specified in the diff, though headers are chrome130+
            proxies={"http": proxy, "https": proxy} if proxy else None,
            timeout=240
        )
        
        # Initialize headers with Cloudflare bypass
        self.headers = self.cloudflare_headers.copy()
        self.headers.update({
            "authority": "grok.com",
            "content-type": "application/json",
            "origin": "https://grok.com",
            "referer": "https://grok.com/?referrer=website",
            "x-statsig-id": self._generate_statsig_id(),
        })
        
        self.set_cookie(self.change_cookie.get_cookie())
        self.set_user_agent(self.change_cookie.get_user_agent())
        logger.info("GrokRequest initialized with curl_cffi (Chrome impersonation)")

    def set_cookie(self, cookie: str) -> None:
        """Set the authentication cookie."""
        self.headers["cookie"] = cookie

    def set_user_agent(self, agent: str) -> None:
        """Set the user agent header."""
        self.headers["user-agent"] = agent
        
    def rotate_credentials(self) -> None:
        """Rotate to the next cookie and user agent."""
        self.set_cookie(self.change_cookie.get_cookie())
        self.set_user_agent(self.change_cookie.get_user_agent())
        logger.info("Credentials rotated to next cookie")
    
    async def _apply_rate_limit(self) -> None:
        """Ensure we don't exceed rate limits."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            wait_time = self.rate_limit_delay - elapsed
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        self.last_request_time = time.time()
    
    def _generate_statsig_id(self) -> str:
        """Generate a realistic x-statsig-id like the browser does."""
        # Generate 80+ random bytes and base64 encode
        random_bytes = secrets.token_bytes(84)
        return base64.b64encode(random_bytes).decode('utf-8').rstrip('=')
    
    def _generate_request_id(self) -> str:
        """Generate a unique request ID (UUID v4)."""
        return str(uuid.uuid4())
    
    def _extract_cf_clearance(self, cookie_string: str) -> Optional[str]:
        """
        Extract cf_clearance token from cookie string for logging.
        
        Args:
            cookie_string: Full cookie string
            
        Returns:
            cf_clearance value or None
        """
        if "cf_clearance=" in cookie_string:
            try:
                return cookie_string.split("cf_clearance=")[1].split(";")[0]
            except IndexError:
                return None
        return None

    async def get_grok_request(
        self, 
        message: str, 
        model: str
    ) -> AsyncGenerator[str, None]:
        """
        Send a request to Grok API and stream the response with Cloudflare bypass.
        
        Args:
            message: The user's message to send
            model: The model name to use (e.g., 'grok-latest', 'grok-3')
            
        Yields:
            Tokens from the streaming response
        """
        await self._apply_rate_limit()
        
        data = {
            "message": message, 
            "modelName": model,
            "disableSearch": False,
            "enableImageGeneration": True,
            "imageAttachments": [],
            "returnImageBytes": False,
            "returnImagePrompt": True,
            "imageGenerationCount": 2,
            "forceConcise": False,
            "toolOverrides": {}
        }
        
        retry_count = 0
        
        # Log cf_clearance presence
        cf_token = self._extract_cf_clearance(self.headers.get("cookie", ""))
        if cf_token:
            logger.info(f"Using cf_clearance: {cf_token}")
        else:
            logger.warning("⚠️  No cf_clearance token found in cookies!")
        
        while retry_count < self.max_retries:
            try:
                # Generate fresh request ID for each attempt
                self.headers["x-xai-request-id"] = self._generate_request_id()
                
                logger.info(f"Sending request to Grok API (attempt {retry_count + 1}/{self.max_retries})")
                logger.info(f"Request ID: {self.headers['x-xai-request-id']}")
                logger.info(f"Request Headers: {json.dumps(self.headers, default=str)}") # Log headers for debugging
                
                # Use curl_cffi stream
                response = await self.session.post(
                    self.grok_url, 
                    headers=self.headers, 
                    json=data,
                    stream=True
                )
                
                if response.status_code == 200:
                    logger.info("✓ Connection established (200 OK)")
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("result", {}).get("response", {}).get("token")
                                if token:
                                    yield token
                            except json.JSONDecodeError:
                                pass
                    logger.info("Stream finished")
                    return  # Success, exit retry loop
                    
                elif response.status_code == 429:
                    # Rate limit - use progressive backoff
                    delay = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                    logger.warning(f"Rate limit hit (429), waiting {delay}s before retry...")
                    await asyncio.sleep(delay)
                    self.rotate_credentials()
                    retry_count += 1
                    continue
                    
                elif response.status_code == 503:
                    # Service unavailable / Cloudflare challenge
                    delay = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                    
                    error_body = b""
                    async for chunk in response.aiter_content():
                        error_body += chunk
                    error_text = error_body.decode()[:500] # Increased log length
                    
                    if "cloudflare" in error_text.lower() or "challenge" in error_text.lower():
                        logger.error(f"Cloudflare challenge detected (503). May need fresh cookies.")
                        logger.info(f"Error body: {error_text}")
                    else:
                        logger.warning(f"Service unavailable (503), waiting {delay}s before retry...")
                    
                    await asyncio.sleep(delay)
                    self.rotate_credentials()
                    retry_count += 1
                    continue
                    
                elif response.status_code in [401, 403]:
                    # Auth failed - could be expired cf_clearance or session
                    delay = self.retry_delays[min(retry_count, len(self.retry_delays) - 1)]
                    
                    error_body = b""
                    async for chunk in response.aiter_content():
                        error_body += chunk
                    error_text = error_body.decode()[:500] # Increased log length
                    
                    logger.error(f"Authentication failed ({response.status_code})")
                    logger.info(f"Error body: {error_text}") # Changed to INFO
                    
                    if "cloudflare" in error_text.lower():
                        logger.error("Cloudflare protection triggered. cf_clearance may be expired.")
                    
                    logger.info(f"Rotating credentials and waiting {delay}s...")
                    await asyncio.sleep(delay)
                    self.rotate_credentials()
                    retry_count += 1
                    continue
                    
                else:
                    # Other errors
                    error_body = b""
                    async for chunk in response.aiter_content():
                        error_body += chunk
                    logger.error(f"Request failed: {response.status_code} - {error_body.decode()[:200]}")
                    yield f"Error: {response.status_code}"
                    return

            except RequestsError as e:
                if "timeout" in str(e).lower():
                    logger.error("Request timeout!")
                else:
                    logger.error(f"Request error: {str(e)}")
                
                retry_count += 1
                if retry_count >= self.max_retries:
                    yield f"Error: Request failed after {self.max_retries} retries"
                    return
                await asyncio.sleep(1) # Add small delay for network errors
                    
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                retry_count += 1
                if retry_count >= self.max_retries:
                    yield f"Error: Unexpected error after {self.max_retries} retries"
                    return
                await asyncio.sleep(1) # Add small delay for unexpected errors
        
        logger.error(f"Max retries ({self.max_retries}) exceeded")
        yield "Error: Maximum retry attempts exceeded"

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("GrokRequest client closed")

