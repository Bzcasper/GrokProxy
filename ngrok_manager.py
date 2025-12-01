#!/usr/bin/env python3
"""Ngrok URL manager - automatically detects and updates the current ngrok URL."""

import json
import time
import logging
from typing import Optional
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class NgrokURLManager:
    """Manages dynamic ngrok URL detection."""
    
    def __init__(self, ngrok_api_url: str = "http://ngrok:4040/api/tunnels"):
        self.ngrok_api_url = ngrok_api_url
        self._cached_url: Optional[str] = None
        self._cache_time: float = 0
        self._cache_ttl: int = 60  # Cache for 60 seconds
    
    def get_public_url(self, force_refresh: bool = False) -> Optional[str]:
        """
        Get the current ngrok public URL.
        
        Args:
            force_refresh: Force refresh even if cached
            
        Returns:
            The public HTTPS URL or None if not available
        """
        # Return cached URL if still valid
        if not force_refresh and self._cached_url and (time.time() - self._cache_time) < self._cache_ttl:
            return self._cached_url
        
        try:
            response = httpx.get(self.ngrok_api_url, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                tunnels = data.get("tunnels", [])
                
                # Find the HTTPS tunnel
                for tunnel in tunnels:
                    if tunnel.get("proto") == "https":
                        url = tunnel.get("public_url")
                        if url:
                            self._cached_url = url
                            self._cache_time = time.time()
                            logger.info(f"✓ Detected ngrok URL: {url}")
                            return url
                
                logger.warning("No HTTPS tunnel found in ngrok API response")
                return None
        
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to ngrok API: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting ngrok URL: {e}")
            return None
    
    def get_base_url(self) -> str:
        """
        Get the base URL for the API (ngrok if available, otherwise local).
        
        Returns:
            The base URL to use
        """
        ngrok_url = self.get_public_url()
        if ngrok_url:
            return ngrok_url
        
        # Fallback to local
        logger.info("Ngrok not available, using local URL")
        return "http://localhost:8080"
    
    def get_endpoint_url(self, endpoint: str = "/v1/chat/completions") -> str:
        """
        Get the full endpoint URL.
        
        Args:
            endpoint: The API endpoint path
            
        Returns:
            Full URL including base and endpoint
        """
        base = self.get_base_url()
        return f"{base}{endpoint}"


# Global instance
ngrok_manager = NgrokURLManager()


def get_current_url() -> Optional[str]:
    """Convenience function to get current ngrok URL."""
    return ngrok_manager.get_public_url()


def get_api_base() -> str:
    """Convenience function to get API base URL."""
    return ngrok_manager.get_base_url()


if __name__ == "__main__":
    # Test the manager
    manager = NgrokURLManager()
    
    print("\n=== Ngrok URL Manager Test ===")
    url = manager.get_public_url()
    if url:
        print(f"✓ Public URL: {url}")
        print(f"✓ Chat endpoint: {manager.get_endpoint_url()}")
    else:
        print("✗ Ngrok not available")
        print(f"✓ Fallback URL: {manager.get_base_url()}")
