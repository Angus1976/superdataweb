"""Tests for the Redis client utilities."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import src.interview.redis_client as rc


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset the module-level Redis client between tests."""
    rc._redis_client = None
    yield
    rc._redis_client = None


class TestGetRedis:
    def test_creates_client_on_first_call(self):
        with patch.object(rc.aioredis, "from_url", return_value=MagicMock()) as mock_from_url:
            client = rc.get_redis()
            mock_from_url.assert_called_once()
            assert client is not None

    def test_returns_same_client_on_subsequent_calls(self):
        with patch.object(rc.aioredis, "from_url", return_value=MagicMock()) as mock_from_url:
            c1 = rc.get_redis()
            c2 = rc.get_redis()
            assert c1 is c2
            mock_from_url.assert_called_once()


class TestSetTokenBlacklist:
    @pytest.mark.asyncio
    async def test_sets_key_with_expiry(self):
        mock_redis = AsyncMock()
        rc._redis_client = mock_redis

        await rc.set_token_blacklist("abc123", 3600)

        mock_redis.setex.assert_awaited_once_with(
            f"{rc.TOKEN_BLACKLIST_PREFIX}abc123", 3600, "1"
        )


class TestIsTokenBlacklisted:
    @pytest.mark.asyncio
    async def test_returns_true_when_key_exists(self):
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        rc._redis_client = mock_redis

        result = await rc.is_token_blacklisted("abc123")

        assert result is True
        mock_redis.exists.assert_awaited_once_with(
            f"{rc.TOKEN_BLACKLIST_PREFIX}abc123"
        )

    @pytest.mark.asyncio
    async def test_returns_false_when_key_missing(self):
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        rc._redis_client = mock_redis

        result = await rc.is_token_blacklisted("missing")

        assert result is False


class TestCloseRedis:
    @pytest.mark.asyncio
    async def test_closes_and_clears_client(self):
        mock_redis = AsyncMock()
        rc._redis_client = mock_redis

        await rc.close_redis()

        mock_redis.aclose.assert_awaited_once()
        assert rc._redis_client is None

    @pytest.mark.asyncio
    async def test_noop_when_no_client(self):
        # Should not raise
        await rc.close_redis()
        assert rc._redis_client is None
