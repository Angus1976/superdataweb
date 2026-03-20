"""Redis client utilities for token blacklist management."""

from __future__ import annotations

import redis.asyncio as aioredis

from src.interview.config import settings

_redis_client: aioredis.Redis | None = None

TOKEN_BLACKLIST_PREFIX = "auth:token_blacklist:"


def get_redis() -> aioredis.Redis:
    """Return the shared async Redis client, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL, decode_responses=True
        )
    return _redis_client


async def set_token_blacklist(token_hash: str, ttl_seconds: int) -> None:
    """Add a token hash to the blacklist with an expiry."""
    client = get_redis()
    key = f"{TOKEN_BLACKLIST_PREFIX}{token_hash}"
    await client.setex(key, ttl_seconds, "1")


async def is_token_blacklisted(token_hash: str) -> bool:
    """Check whether a token hash is present in the blacklist."""
    client = get_redis()
    key = f"{TOKEN_BLACKLIST_PREFIX}{token_hash}"
    return bool(await client.exists(key))


async def close_redis() -> None:
    """Close the Redis connection if open."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
