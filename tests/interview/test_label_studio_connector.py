"""Tests for LabelStudioConnector — sync labels to Label Studio."""

import pytest

from src.interview.label_studio_connector import LabelStudioConnector, SyncResult
from src.interview.models import AIFriendlyLabel, Entity, Relation, Rule


class FakeLSClient:
    """Fake Label Studio client for testing."""
    pass


@pytest.fixture()
def connector_no_client() -> LabelStudioConnector:
    return LabelStudioConnector()


@pytest.fixture()
def connector_with_client() -> LabelStudioConnector:
    return LabelStudioConnector(ls_client=FakeLSClient())


@pytest.fixture()
def sample_label() -> AIFriendlyLabel:
    return AIFriendlyLabel(
        entities=[
            Entity(id="e1", name="Customer", type="person"),
            Entity(id="e2", name="Order", type="object"),
        ],
        rules=[Rule(id="R1", name="r", condition="c", action="a")],
        relations=[Relation(id="rel1", source_entity="e1", target_entity="e2", relation_type="has")],
    )


class TestCheckConnection:
    @pytest.mark.asyncio
    async def test_no_client_returns_false(self, connector_no_client):
        assert await connector_no_client.check_connection() is False

    @pytest.mark.asyncio
    async def test_with_client_returns_true(self, connector_with_client):
        assert await connector_with_client.check_connection() is True


class TestSyncLabels:
    @pytest.mark.asyncio
    async def test_sync_without_client_raises(self, connector_no_client, sample_label):
        with pytest.raises(ConnectionError, match="Cannot connect"):
            await connector_no_client.sync_labels("p1", sample_label)

    @pytest.mark.asyncio
    async def test_sync_with_client(self, connector_with_client, sample_label):
        result = await connector_with_client.sync_labels("p1", sample_label)
        assert isinstance(result, SyncResult)
        assert result.success_count == 2  # 2 entities
        assert result.has_predictions is True
        assert len(result.task_ids) == 2

    @pytest.mark.asyncio
    async def test_sync_empty_label(self, connector_with_client):
        result = await connector_with_client.sync_labels("p1", AIFriendlyLabel())
        assert result.success_count == 0
        assert result.task_ids == []


class TestToLSTasks:
    def test_task_format(self, sample_label):
        tasks = LabelStudioConnector._to_ls_tasks(sample_label)
        assert len(tasks) == 2
        task = tasks[0]
        assert "predictions" in task
        assert task["predictions"][0]["model_version"] == "interview-ai-v1"
        assert "data" in task
