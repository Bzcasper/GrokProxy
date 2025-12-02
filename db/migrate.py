#!/usr/bin/env python3
"""
Database migration runner for GrokProxy.

Usage:
    python db/migrate.py          # Apply all pending migrations
    python db/migrate.py --dry    # Show pending migrations without applying
"""

import os
import sys
import asyncio
import argparse
import logging
from pathlib import Path

import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MigrationRunner:
    """Manages database schema migrations."""
    
    def __init__(self, database_url: str, migrations_dir: Path):
        """
        Initialize migration runner.
        
        Args:
            database_url: PostgreSQL connection string
            migrations_dir: Directory containing migration SQL files
        """
        self.database_url = database_url
        self.migrations_dir = migrations_dir
    
    async def get_applied_migrations(self, conn: asyncpg.Connection) -> set:
        """Get set of already applied migration versions."""
        # Check if migrations table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'schema_migrations'
            )
            """
        )
        
        if not table_exists:
            return set()
        
        rows = await conn.fetch("SELECT version FROM schema_migrations ORDER BY version")
        return {row["version"] for row in rows}
    
    def get_migration_files(self) -> list:
        """
        Get sorted list of migration SQL files.
        
        Returns:
            List of tuples (version, name, path)
        """
        migrations = []
        
        if not self.migrations_dir.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_dir}")
            return migrations
        
        for file_path in sorted(self.migrations_dir.glob("*.sql")):
            filename = file_path.stem
            
            # Extract version number from filename (e.g., "001_create_tables" -> 1)
            try:
                version_str = filename.split("_")[0]
                version = int(version_str)
                name = filename
                migrations.append((version, name, file_path))
            except (ValueError, IndexError):
                logger.warning(f"Skipping invalid migration filename: {filename}")
        
        return sorted(migrations, key=lambda x: x[0])
    
    async def apply_migration(
        self,
        conn: asyncpg.Connection,
        version: int,
        name: str,
        file_path: Path
    ) -> None:
        """Apply a single migration."""
        logger.info(f"Applying migration {version}: {name}")
        
        # Read migration SQL
        with open(file_path, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Execute migration (note: migration file should handle its own transaction)
        await conn.execute(sql)
        
        logger.info(f"✓ Migration {version} applied successfully")
    
    async def run(self, dry_run: bool = False) -> None:
        """
        Run all pending migrations.
        
        Args:
            dry_run: If True, only show pending migrations without applying
        """
        logger.info("Starting migration runner...")
        
        # Get all migration files
        all_migrations = self.get_migration_files()
        if not all_migrations:
            logger.info("No migration files found")
            return
        
        logger.info(f"Found {len(all_migrations)} migration file(s)")
        
        # Connect to database
        try:
            conn = await asyncpg.connect(self.database_url)
            logger.info("✓ Connected to database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            sys.exit(1)
        
        try:
            # Get applied migrations
            applied = await self.get_applied_migrations(conn)
            logger.info(f"Found {len(applied)} applied migration(s)")
            
            # Find pending migrations
            pending = [
                (v, n, p) for v, n, p in all_migrations
                if v not in applied
            ]
            
            if not pending:
                logger.info("✓ All migrations are up to date")
                return
            
            logger.info(f"Found {len(pending)} pending migration(s):")
            for version, name, _ in pending:
                logger.info(f"  - {version}: {name}")
            
            if dry_run:
                logger.info("Dry run mode - no migrations applied")
                return
            
            # Apply pending migrations
            for version, name, file_path in pending:
                await self.apply_migration(conn, version, name, file_path)
            
            logger.info(f"✓ Successfully applied {len(pending)} migration(s)")
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            sys.exit(1)
        finally:
            await conn.close()
            logger.info("Database connection closed")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run database migrations")
    parser.add_argument(
        "--dry",
        action="store_true",
        help="Dry run - show pending migrations without applying"
    )
    parser.add_argument(
        "--database-url",
        help="PostgreSQL connection string (defaults to DATABASE_URL env var)"
    )
    args = parser.parse_args()
    
    # Get database URL
    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL must be provided via --database-url or environment variable")
        sys.exit(1)
    
    # Get migrations directory
    project_root = Path(__file__).parent.parent
    migrations_dir = project_root / "db" / "migrations"
    
    # Run migrations
    runner = MigrationRunner(database_url, migrations_dir)
    await runner.run(dry_run=args.dry)


if __name__ == "__main__":
    asyncio.run(main())
