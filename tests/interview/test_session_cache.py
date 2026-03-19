"""Tests for SessionCache — in-memory fallback."""

import pytest

from src.interview.session_cache import SessionCache


@pytest.fixture()
def cache() -> SessionCache:
    return SessionCache()


class TestContextManagement:
    @pytest.mark.asyncio
    async def test_save_and_load(self, cache):
        await cache.save_context("s1", {"round": 1})
        ctx = await cache.load_context("s1")
        assert ctx == {"round": 1}

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, cache):
        assert await cache.load_context("nope") is None

    @pytest.mark.asyncio
    async def test_delete_context(self, cache):
        await cache.save_context("s1", {"round": 1})
        await cache.delete_context("s1")
        assert await cache.load_context("s1") is None


class TestLocking:
    @pytest.mark.asyncio
    async def test_acquire_and_release(self, cache):
        assert await cache.acquire_lock("s1") is True
        assert await cache.acquire_lock("s1") is False  # already locked
        await cache.release_lock("s1")
        assert await cache.acquire_lock("s1") is True  # re-acquired

    @pytest.mark.asyncio
    async def test_different_sessions_independent(self, cache):
        assert await cache.acquire_lock("s1") is True
        assert await cache.acquire_lock("s2") is True


class TestTaskStatus:
    @pytest.mark.asyncio
    async def test_update_and_get(self, cache):
        await cache.update_task_status("t1", "processing")
        status = await cache.get_task_status("t1")
        assert status["status"] == "processing"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, cache):
        assert await cache.get_task_status("nope") is None
