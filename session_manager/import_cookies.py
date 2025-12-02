#!/usr/bin/env python3
"""
Script to import cookies from cookies.yaml into the database.

Usage:
    python -m session_manager.import_cookies
"""

import asyncio
import sys
import yaml
import hashlib
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.client import DatabaseClient
from session_manager.models import SessionCreate
from observability.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


async def import_from_yaml(yaml_path: str = "cookies.yaml") -> None:
    """
    Import cookies from YAML file into database.
    
    Args:
        yaml_path: Path to cookies.yaml file
    """
    # Load YAML
    logger.info(f"Loading cookies from {yaml_path}")
    
    with open(yaml_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    cookies = config.get("cookies", [])
    
    if not cookies:
        logger.warning("No cookies found in YAML file")
        return
    
    logger.info(f"Found {len(cookies)} cookies to import")
    
    # Connect to database
    db = DatabaseClient()
    await db.connect()
    
    try:
        imported = 0
        skipped = 0
        
        for cookie_text in cookies:
            # Generate hash
            cookie_hash = hashlib.sha256(cookie_text.encode()).hexdigest()
            
            # Check if already exists
            sessions = await db.list_sessions(limit=1000)
            exists = any(s["cookie_hash"] == cookie_hash for s in sessions)
            
            if exists:
                logger.info(f"Cookie already exists (hash: {cookie_hash[:8]}...), skipping")
                skipped += 1
                continue
            
            # Create session
            session_id = await db.create_session(
                cookie_text=cookie_text,
                cookie_hash=cookie_hash,
                provider="grok",
                metadata=None
            )
            
            imported += 1
            logger.info(f"Imported session {session_id[:8]}...")
        
        logger.info(f"✓ Import complete: {imported} imported, {skipped} skipped")
        
    finally:
        await db.disconnect()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Import cookies from YAML to database")
    parser.add_argument(
        "--file",
        default="cookies.yaml",
        help="Path to cookies.yaml file"
    )
    args = parser.parse_args()
    
    asyncio.run(import_from_yaml(args.file))
