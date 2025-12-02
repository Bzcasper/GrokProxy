"""
Utility script to manually update Vercel environment variables.
Can be used standalone or imported by other scripts.
"""

import os
import sys
import argparse
import httpx
import asyncio
from typing import Optional, List


class VercelEnvUpdater:
    """Client for updating Vercel environment variables."""
    
    def __init__(
        self,
        api_token: str,
        project_id: str,
        team_id: Optional[str] = None
    ):
        """
        Initialize the Vercel API client.
        
        Args:
            api_token: Vercel API token
            project_id: Vercel project ID
            team_id: Optional team ID
        """
        self.api_token = api_token
        self.project_id = project_id
        self.team_id = team_id
        self.base_url = "https://api.vercel.com"
        self.client = httpx.AsyncClient(timeout=30.0)
    
    def _get_headers(self) -> dict:
        """Get API request headers."""
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    def _get_endpoint(self, path: str = "") -> str:
        """Get API endpoint URL."""
        base = f"{self.base_url}/v9/projects/{self.project_id}/env"
        if path:
            base = f"{base}/{path}"
        if self.team_id:
            base = f"{base}?teamId={self.team_id}"
        return base
    
    async def list_env_vars(self) -> List[dict]:
        """List all environment variables for the project."""
        endpoint = self._get_endpoint()
        response = await self.client.get(endpoint, headers=self._get_headers())
        response.raise_for_status()
        
        data = response.json()
        return data.get('envs', [])
    
    async def get_env_var(self, key: str) -> Optional[dict]:
        """Get a specific environment variable by key."""
        env_vars = await self.list_env_vars()
        for var in env_vars:
            if var.get('key') == key:
                return var
        return None
    
    async def create_env_var(
        self,
        key: str,
        value: str,
        targets: Optional[List[str]] = None
    ) -> dict:
        """
        Create a new environment variable.
        
        Args:
            key: Environment variable name
            value: Environment variable value
            targets: List of targets (production, preview, development)
        
        Returns:
            Created environment variable data
        """
        if targets is None:
            targets = ["production", "preview", "development"]
        
        endpoint = self._get_endpoint()
        payload = {
            "key": key,
            "value": value,
            "type": "plain",
            "target": targets
        }
        
        response = await self.client.post(
            endpoint,
            headers=self._get_headers(),
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    async def update_env_var(
        self,
        key: str,
        value: str,
        targets: Optional[List[str]] = None
    ) -> dict:
        """
        Update an existing environment variable.
        
        Args:
            key: Environment variable name
            value: New value
            targets: List of targets to update
        
        Returns:
            Updated environment variable data
        """
        # Get existing variable
        existing = await self.get_env_var(key)
        if not existing:
            raise ValueError(f"Environment variable '{key}' not found")
        
        if targets is None:
            targets = ["production", "preview", "development"]
        
        var_id = existing['id']
        endpoint = self._get_endpoint(var_id)
        payload = {
            "value": value,
            "target": targets
        }
        
        response = await self.client.patch(
            endpoint,
            headers=self._get_headers(),
            json=payload
        )
        response.raise_for_status()
        
        return response.json()
    
    async def upsert_env_var(
        self,
        key: str,
        value: str,
        targets: Optional[List[str]] = None
    ) -> dict:
        """
        Create or update an environment variable.
        
        Args:
            key: Environment variable name
            value: Environment variable value
            targets: List of targets
        
        Returns:
            Environment variable data
        """
        existing = await self.get_env_var(key)
        
        if existing:
            print(f"Updating existing variable: {key}")
            return await self.update_env_var(key, value, targets)
        else:
            print(f"Creating new variable: {key}")
            return await self.create_env_var(key, value, targets)
    
    async def delete_env_var(self, key: str) -> bool:
        """Delete an environment variable."""
        existing = await self.get_env_var(key)
        if not existing:
            print(f"Variable '{key}' not found")
            return False
        
        var_id = existing['id']
        endpoint = self._get_endpoint(var_id)
        
        response = await self.client.delete(
            endpoint,
            headers=self._get_headers()
        )
        response.raise_for_status()
        
        return True
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Update Vercel environment variables"
    )
    parser.add_argument(
        "--token",
        default=os.getenv("VERCEL_API_TOKEN"),
        help="Vercel API token (or set VERCEL_API_TOKEN env var)"
    )
    parser.add_argument(
        "--project-id",
        default=os.getenv("VERCEL_PROJECT_ID"),
        help="Vercel project ID (or set VERCEL_PROJECT_ID env var)"
    )
    parser.add_argument(
        "--team-id",
        default=os.getenv("VERCEL_TEAM_ID"),
        help="Vercel team ID (optional)"
    )
    parser.add_argument(
        "--key",
        required=True,
        help="Environment variable key"
    )
    parser.add_argument(
        "--value",
        required=True,
        help="Environment variable value"
    )
    parser.add_argument(
        "--targets",
        nargs="+",
        default=["production", "preview", "development"],
        help="Deployment targets"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be done without making changes"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all environment variables"
    )
    
    args = parser.parse_args()
    
    if not args.token:
        print("Error: Vercel API token required (--token or VERCEL_API_TOKEN)")
        sys.exit(1)
    
    if not args.project_id:
        print("Error: Project ID required (--project-id or VERCEL_PROJECT_ID)")
        sys.exit(1)
    
    updater = VercelEnvUpdater(
        api_token=args.token,
        project_id=args.project_id,
        team_id=args.team_id
    )
    
    try:
        if args.list:
            # List all variables
            env_vars = await updater.list_env_vars()
            print(f"\nFound {len(env_vars)} environment variables:\n")
            for var in env_vars:
                print(f"  {var['key']}: {var.get('value', '[encrypted]')}")
                print(f"    Targets: {', '.join(var.get('target', []))}")
                print()
        elif args.dry_run:
            # Dry run
            print(f"\n[DRY RUN] Would update environment variable:")
            print(f"  Key: {args.key}")
            print(f"  Value: {args.value}")
            print(f"  Targets: {', '.join(args.targets)}")
            print()
        else:
            # Update variable
            result = await updater.upsert_env_var(
                key=args.key,
                value=args.value,
                targets=args.targets
            )
            print(f"\n✓ Successfully updated {args.key}")
            print(f"  Value: {args.value}")
            print(f"  Targets: {', '.join(args.targets)}")
            print()
    finally:
        await updater.close()


if __name__ == "__main__":
    asyncio.run(main())
