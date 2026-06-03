"""
LogSentry - Database connection pool and session management.
Uses asyncpg for async PostgreSQL operations.
"""

import os
import asyncpg
from contextlib import asynccontextmanager
from typing import Optional


class DatabasePool:
    """Manages async PostgreSQL connection pool."""

    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def get_pool(cls) -> asyncpg.Pool:
        """Get or create the connection pool."""
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                host=os.getenv("POSTGRES_HOST", "postgres"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB", "logsentry"),
                user=os.getenv("POSTGRES_USER", "logsentry"),
                password=os.getenv("POSTGRES_PASSWORD", "logsentry_secret_2024"),
                min_size=5,
                max_size=20,
                command_timeout=30,
                statement_cache_size=100,
            )
        return cls._pool

    @classmethod
    async def close(cls):
        """Close the connection pool."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None

    @classmethod
    @asynccontextmanager
    async def acquire(cls):
        """Acquire a connection from the pool."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            yield conn

    @classmethod
    @asynccontextmanager
    async def transaction(cls):
        """Acquire a connection and start a transaction."""
        pool = await cls.get_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn


class RedisConnection:
    """Manages async Redis connection."""

    _redis = None

    @classmethod
    async def get_redis(cls):
        """Get or create the Redis connection."""
        if cls._redis is None:
            import redis.asyncio as aioredis
            cls._redis = aioredis.Redis(
                host=os.getenv("REDIS_HOST", "redis"),
                port=int(os.getenv("REDIS_PORT", "6379")),
                password=os.getenv("REDIS_PASSWORD", None) or None,
                decode_responses=True,
                max_connections=20,
            )
        return cls._redis

    @classmethod
    async def close(cls):
        """Close the Redis connection."""
        if cls._redis:
            await cls._redis.close()
            cls._redis = None
