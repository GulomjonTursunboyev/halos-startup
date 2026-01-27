"""
Database connection for Mobile API
Uses the same PostgreSQL database as the Telegram bot
"""

import asyncpg
import logging
from typing import Optional
from api.config import settings

logger = logging.getLogger(__name__)

# Global pool
_pool: Optional[asyncpg.Pool] = None


async def init_db():
    """Initialize database connection pool"""
    global _pool
    
    db_url = settings.DATABASE_URL
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    
    try:
        _pool = await asyncpg.create_pool(
            dsn=db_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
            ssl='require',
            max_inactive_connection_lifetime=60
        )
        logger.info("Database pool created successfully")
    except Exception as e:
        logger.error(f"Failed to create database pool: {e}")
        raise


async def close_db():
    """Close database connection pool"""
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def get_pool() -> asyncpg.Pool:
    """Get database pool"""
    if _pool is None:
        await init_db()
    return _pool


async def get_connection():
    """Get a database connection from pool"""
    pool = await get_pool()
    return pool.acquire()
