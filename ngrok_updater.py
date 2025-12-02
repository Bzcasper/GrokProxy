"""
Ngrok URL Updater Service
Automatically detects ngrok URL changes and updates Vercel environment variables.
"""

import os
import sys
import time
import yaml
import httpx
import asyncio
from typing import Optional, Dict
from pathlib import Path


class NgrokUpdater:
    """Service to monitor ngrok URL and update Vercel environment variables."""
    
    def __init__(self, config_path: str = "ngrok_updater_config.yaml"):
        """Initialize the updater with configuration."""
        self.config = self._load_config(config_path)
        self.current_url: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=30.0)
        
        # Vercel API configuration
        self.vercel_token = self.config['vercel']['api_token']
        self.project_id = self.config['vercel']['project_id']
        self.team_id = self.config['vercel'].get('team_id')
        self.env_var_name = self.config['vercel'].get('env_var_name', 'NGROK_PROXY_URL')
        
        # Ngrok configuration
        self.ngrok_api_url = self.config['ngrok']['api_url']
        self.poll_interval = self.config['ngrok'].get('poll_interval', 30)
        
        # Logging
        self.log_level = self.config.get('logging', {}).get('level', 'INFO')
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from YAML file."""
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_file, 'r') as f:
            return yaml.safe_load(f)
    
    def _log(self, level: str, message: str):
        """Simple logging."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}", flush=True)
    
    async def get_ngrok_url(self) -> Optional[str]:
        """Fetch the current ngrok URL from the ngrok API."""
        try:
            response = await self.client.get(self.ngrok_api_url)
            response.raise_for_status()
            
            data = response.json()
            tunnels = data.get('tunnels', [])
            
            if not tunnels:
                self._log("WARNING", "No active ngrok tunnels found")
                return None
            
            # Get the first HTTPS tunnel
            for tunnel in tunnels:
                if tunnel.get('proto') == 'https':
                    url = tunnel.get('public_url')
                    self._log("DEBUG", f"Found ngrok URL: {url}")
                    return url
            
            # Fallback to first tunnel
            url = tunnels[0].get('public_url')
            self._log("DEBUG", f"Using first tunnel URL: {url}")
            return url
            
        except httpx.HTTPError as e:
            self._log("ERROR", f"Failed to fetch ngrok URL: {e}")
            return None
        except Exception as e:
            self._log("ERROR", f"Unexpected error fetching ngrok URL: {e}")
            return None
    
    async def update_vercel_env(self, url: str) -> bool:
        """Update Vercel environment variable with new ngrok URL."""
        try:
            # Vercel API endpoint
            base_url = "https://api.vercel.com"
            if self.team_id:
                endpoint = f"{base_url}/v9/projects/{self.project_id}/env?teamId={self.team_id}"
            else:
                endpoint = f"{base_url}/v9/projects/{self.project_id}/env"
            
            headers = {
                "Authorization": f"Bearer {self.vercel_token}",
                "Content-Type": "application/json"
            }
            
            # First, try to get existing env var
            self._log("INFO", f"Checking for existing env var: {self.env_var_name}")
            response = await self.client.get(endpoint, headers=headers)
            response.raise_for_status()
            
            env_vars = response.json().get('envs', [])
            existing_var = None
            
            for var in env_vars:
                if var.get('key') == self.env_var_name:
                    existing_var = var
                    break
            
            if existing_var:
                # Update existing variable
                var_id = existing_var['id']
                update_endpoint = f"{endpoint}/{var_id}"
                
                payload = {
                    "value": url,
                    "target": ["production", "preview", "development"]
                }
                
                self._log("INFO", f"Updating existing env var {self.env_var_name}")
                response = await self.client.patch(update_endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                self._log("INFO", f"Successfully updated {self.env_var_name} to {url}")
                return True
            else:
                # Create new variable
                payload = {
                    "key": self.env_var_name,
                    "value": url,
                    "type": "plain",
                    "target": ["production", "preview", "development"]
                }
                
                self._log("INFO", f"Creating new env var {self.env_var_name}")
                response = await self.client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                
                self._log("INFO", f"Successfully created {self.env_var_name} with value {url}")
                return True
                
        except httpx.HTTPError as e:
            self._log("ERROR", f"Failed to update Vercel env var: {e}")
            if hasattr(e, 'response') and e.response:
                self._log("ERROR", f"Response: {e.response.text}")
            return False
        except Exception as e:
            self._log("ERROR", f"Unexpected error updating Vercel: {e}")
            return False
    
    async def run(self):
        """Main loop to monitor ngrok and update Vercel."""
        self._log("INFO", f"Starting ngrok updater service (polling every {self.poll_interval}s)")
        
        while True:
            try:
                # Get current ngrok URL
                url = await self.get_ngrok_url()
                
                if url and url != self.current_url:
                    self._log("INFO", f"Ngrok URL changed: {self.current_url} -> {url}")
                    
                    # Update Vercel
                    success = await self.update_vercel_env(url)
                    
                    if success:
                        self.current_url = url
                        self._log("INFO", "Vercel environment variable updated successfully")
                    else:
                        self._log("ERROR", "Failed to update Vercel environment variable")
                elif url == self.current_url:
                    self._log("DEBUG", f"Ngrok URL unchanged: {url}")
                else:
                    self._log("WARNING", "No ngrok URL available")
                
            except Exception as e:
                self._log("ERROR", f"Error in main loop: {e}")
            
            # Wait before next check
            await asyncio.sleep(self.poll_interval)
    
    async def close(self):
        """Cleanup resources."""
        await self.client.aclose()


async def main():
    """Entry point for the updater service."""
    config_path = os.getenv("NGROK_UPDATER_CONFIG", "ngrok_updater_config.yaml")
    
    updater = NgrokUpdater(config_path)
    
    try:
        await updater.run()
    except KeyboardInterrupt:
        print("\nShutting down ngrok updater...")
    finally:
        await updater.close()


if __name__ == "__main__":
    asyncio.run(main())
