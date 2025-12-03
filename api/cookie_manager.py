"""
Cookie Manager for GrokProxy Vercel Deployment.
Loads cookies from environment variables and manages automatic rotation.
"""

import os
import logging
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from threading import Lock
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class CookieInfo:
    """Information about a single cookie."""
    index: int
    cookie_value: str
    user_agent: str
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    healthy: bool = True
    error_types: Dict[str, int] = field(default_factory=dict)


class CookieManager:
    """
    Manages multiple Grok cookies from environment variables.
    Provides automatic rotation on failures and rate limits.
    """
    
    # Default user agents pool
    DEFAULT_USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]
    
    def __init__(self, failure_threshold: int = 3):
        """
        Initialize cookie manager.
        
        Args:
            failure_threshold: Number of failures before marking cookie unhealthy
        """
        self.failure_threshold = failure_threshold
        self.cookies: List[CookieInfo] = []
        self.current_index = 0
        self.lock = Lock()
        
        # Load cookies from environment
        self._load_cookies_from_env()
        
        if not self.cookies:
            logger.warning("No cookies loaded from environment variables!")
        else:
            logger.info(f"Loaded {len(self.cookies)} cookie(s) from environment")
    
    def _load_cookies_from_env(self):
        """Load cookies from COOKIE_1, COOKIE_2, ... environment variables."""
        cookie_index = 1
        
        while True:
            cookie_env_var = f"COOKIE_{cookie_index}"
            cookie_value = os.getenv(cookie_env_var)
            
            if not cookie_value:
                # No more cookies
                break
            
            # Check for custom user agent for this cookie
            user_agent_env_var = f"USER_AGENT_{cookie_index}"
            user_agent = os.getenv(user_agent_env_var)
            
            if not user_agent:
                # Use random default user agent
                user_agent = random.choice(self.DEFAULT_USER_AGENTS)
            
            cookie_info = CookieInfo(
                index=cookie_index - 1,  # 0-indexed
                cookie_value=cookie_value.strip(),
                user_agent=user_agent
            )
            
            self.cookies.append(cookie_info)
            logger.info(f"Loaded {cookie_env_var}")
            
            cookie_index += 1
    
    def get_next_cookie(self) -> Dict[str, Any]:
        """
        Get the next available cookie for use (round-robin).
        
        Returns:
            Dict with cookie info: {index, cookie, user_agent, cookies_dict}
            
        Raises:
            RuntimeError: If no healthy cookies available
        """
        with self.lock:
            if not self.cookies:
                raise RuntimeError("No cookies configured")
            
            # Find next healthy cookie (round-robin)
            attempts = 0
            while attempts < len(self.cookies):
                cookie = self.cookies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.cookies)
                
                if cookie.healthy:
                    cookie.last_used = datetime.utcnow()
                    
                    # Parse cookie value to extract key-value
                    # Expected format: "sso=VALUE"
                    cookies_dict = {}
                    if "=" in cookie.cookie_value:
                        key, value = cookie.cookie_value.split("=", 1)
                        cookies_dict[key.strip()] = value.strip()
                    else:
                        # Assume it's just the SSO value
                        cookies_dict["sso"] = cookie.cookie_value.strip()
                    
                    return {
                        "index": cookie.index,
                        "cookie": cookie.cookie_value,
                        "user_agent": cookie.user_agent,
                        "cookies_dict": cookies_dict
                    }
                
                attempts += 1
            
            # No healthy cookies found, use any available (last resort)
            if self.cookies:
                logger.warning("No healthy cookies available, using any cookie as fallback")
                cookie = self.cookies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.cookies)
                cookie.last_used = datetime.utcnow()
                
                cookies_dict = {}
                if "=" in cookie.cookie_value:
                    key, value = cookie.cookie_value.split("=", 1)
                    cookies_dict[key.strip()] = value.strip()
                else:
                    cookies_dict["sso"] = cookie.cookie_value.strip()
                
                return {
                    "index": cookie.index,
                    "cookie": cookie.cookie_value,
                    "user_agent": cookie.user_agent,
                    "cookies_dict": cookies_dict
                }
            
            raise RuntimeError("No cookies available")
    
    def mark_cookie_success(self, cookie_index: int):
        """
        Mark a cookie as successful.
        
        Args:
            cookie_index: Index of the cookie
        """
        with self.lock:
            if cookie_index < len(self.cookies):
                cookie = self.cookies[cookie_index]
                cookie.success_count += 1
                cookie.failure_count = 0  # Reset failures on success
                cookie.healthy = True
                logger.debug(f"Cookie {cookie_index} marked successful (total: {cookie.success_count})")
    
    def mark_cookie_failed(self, cookie_index: int, error_type: str = "unknown"):
        """
        Mark a cookie as failed and check if it should be marked unhealthy.
        
        Args:
            cookie_index: Index of the cookie
            error_type: Type of error (rate_limit, auth_failed, timeout, etc.)
        """
        with self.lock:
            if cookie_index < len(self.cookies):
                cookie = self.cookies[cookie_index]
                cookie.failure_count += 1
                
                # Track error type
                if error_type not in cookie.error_types:
                    cookie.error_types[error_type] = 0
                cookie.error_types[error_type] += 1
                
                # Check if should be marked unhealthy
                if cookie.failure_count >= self.failure_threshold:
                    cookie.healthy = False
                    logger.warning(
                        f"Cookie {cookie_index} marked UNHEALTHY after {cookie.failure_count} failures "
                        f"(errors: {cookie.error_types})"
                    )
                else:
                    logger.warning(
                        f"Cookie {cookie_index} failed ({error_type}): "
                        f"{cookie.failure_count}/{self.failure_threshold}"
                    )
    
    def get_cookie_stats(self) -> List[Dict[str, Any]]:
        """
        Get statistics for all cookies.
        
        Returns:
            List of cookie stats dictionaries
        """
        with self.lock:
            stats = []
            for cookie in self.cookies:
                stats.append({
                    "index": cookie.index,
                    "healthy": cookie.healthy,
                    "success_count": cookie.success_count,
                    "failure_count": cookie.failure_count,
                    "last_used": cookie.last_used.isoformat() if cookie.last_used else None,
                    "error_types": dict(cookie.error_types),
                    "cookie_preview": cookie.cookie_value[:20] + "..." if len(cookie.cookie_value) > 20 else cookie.cookie_value
                })
            return stats
    
    def get_healthy_count(self) -> int:
        """Get count of healthy cookies."""
        with self.lock:
            return sum(1 for c in self.cookies if c.healthy)
    
    def get_total_count(self) -> int:
        """Get total count of cookies."""
        return len(self.cookies)
    
    def reset_cookie_health(self, cookie_index: int):
        """
        Manually reset a cookie's health status.
        
        Args:
            cookie_index: Index of the cookie
        """
        with self.lock:
            if cookie_index < len(self.cookies):
                cookie = self.cookies[cookie_index]
                cookie.healthy = True
                cookie.failure_count = 0
                cookie.error_types.clear()
                logger.info(f"Cookie {cookie_index} health reset")
