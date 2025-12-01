import yaml
import random
import logging
import threading
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ChangeCookie:
    """Thread-safe cookie and user-agent rotation manager."""
    
    def __init__(self, config_path: str = 'cookies.yaml'):
        """
        Initialize the cookie rotation manager.
        
        Args:
            config_path: Path to the cookies configuration file
        """
        self.config_path = Path(config_path)
        self.cookies_sum = 0
        self.cookie_count = 0
        self.lock = threading.Lock()  # Thread-safe rotation
        
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config = yaml.safe_load(file)
            
            # Validate configuration
            if not self.config:
                raise ValueError("Configuration file is empty")
            
            if 'cookies' not in self.config:
                raise ValueError("'cookies' key not found in configuration")
            
            if 'user_agent' not in self.config:
                raise ValueError("'user_agent' key not found in configuration")
            
            # Load cookies and user agents
            self.cookies = self.config['cookies']
            self.cookies_sum = len(self.cookies)
            self.user_agent = self.config['user_agent']
            
            if self.cookies_sum == 0:
                raise ValueError("No cookies found in configuration")
            
            if len(self.user_agent) == 0:
                raise ValueError("No user agents found in configuration")
            
            logger.info(f"✓ Loaded {self.cookies_sum} cookies and {len(self.user_agent)} user agents")
            
        except FileNotFoundError as e:
            logger.error(f"Configuration file error: {e}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error loading configuration: {e}")
            raise

    def get_user_agent(self) -> str:
        """
        Get a random user agent from the pool.
        
        Returns:
            A randomly selected user agent string
        """
        agent = random.choice(self.user_agent)
        logger.debug(f"Selected user agent: {agent[:50]}...")
        return agent

    def get_cookie(self) -> str:
        """
        Get the next cookie in rotation (thread-safe).
        
        Returns:
            The next cookie string in the rotation
        """
        with self.lock:
            current_index = self.cookie_count
            logger.info(f"Cookie rotation: {current_index + 1}/{self.cookies_sum}")
            
            # Get current cookie
            cookie = self.cookies[current_index]
            
            # Increment counter with wrap-around
            self.cookie_count = (self.cookie_count + 1) % self.cookies_sum
            
            return cookie

    def reset_rotation(self) -> None:
        """Reset cookie rotation to the beginning."""
        with self.lock:
            self.cookie_count = 0
            logger.info("Cookie rotation reset to beginning")

    def reload_config(self) -> None:
        """Reload configuration from file."""
        logger.info("Reloading configuration...")
        self._load_config()

    def get_stats(self) -> dict:
        """
        Get statistics about the cookie manager.
        
        Returns:
            Dictionary with stats (total cookies, current position, etc.)
        """
        return {
            'total_cookies': self.cookies_sum,
            'current_position': self.cookie_count,
            'total_user_agents': len(self.user_agent),
            'config_path': str(self.config_path)
        }


if __name__ == '__main__':
    # Test the cookie manager
    try:
        manager = ChangeCookie()
        
        print("\n=== Cookie Manager Stats ===")
        stats = manager.get_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
        
        print("\n=== Testing User Agents ===")
        for i in range(3):
            print(f"{i+1}. {manager.get_user_agent()}")
        
        print("\n=== Testing Cookie Rotation ===")
        for i in range(5):
            cookie = manager.get_cookie()
            print(f"{i+1}. {cookie[:80]}...")
            
    except Exception as e:
        logger.error(f"Test failed: {e}")
