"""Tests for Celery async tasks."""

import pytest

from src.interview.session_cache import SessionCache
from src.interview.tasks import extract_entities_task, generate_labels_task


@pytest.fixture()
def cache() -> SessionCache:
    return SessionCache()


class TestExtractEntitiesTask:
    @pytest.mark.asyncio
    async def test_returns_result(self, cache):
        result = await extract_entities_task(
            "s1", "m1", "测试消息", [], _cache=cache
        )
        assert "entities" in result

    @pytest.mark.asyncio
    async def test_updates_cache_status(self, cache):
        await extract_entities_task("s1", "m1", "msg", [], _cache=cache)
        status = await cache.get_task_status("extract:m1")
        assert status["status"] == "completed"


class TestGenerateLabelsTask:
    @pytest.mark.asyncio
    async def test_returns_result(self, cache):
        result = await generate_labels_task("p1", "t1", _cache=cache)
        assert result["status"] == "completed"
