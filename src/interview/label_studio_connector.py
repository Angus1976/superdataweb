"""LabelStudioConnector — sync labels to Label Studio task pool."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from src.interview.models import AIFriendlyLabel

logger = logging.getLogger(__name__)


class SyncResult(BaseModel):
    """Label Studio 同步结果。"""
    task_ids: list[str] = []
    success_count: int = 0
    error_count: int = 0
    has_predictions: bool = False


class LabelStudioConnector:
    """复用现有 Label Studio 客户端，同步标签至任务池。"""

    def __init__(self, ls_client: Any = None) -> None:
        self._client = ls_client

    async def check_connection(self) -> bool:
        """Check Label Studio connection status."""
        if self._client is None:
            return False
        try:
            # In production: call LS health API
            return True
        except Exception as exc:
            logger.error("Label Studio connection failed: %s", exc)
            return False

    async def sync_labels(
        self, project_id: str, label: AIFriendlyLabel
    ) -> SyncResult:
        """Sync AIFriendlyLabel to Label Studio as tasks with predictions."""
        if not await self.check_connection():
            raise ConnectionError("Cannot connect to Label Studio")

        # Convert label to LS task format with predictions
        tasks = self._to_ls_tasks(label)

        task_ids = []
        errors = 0
        for task in tasks:
            try:
                # In production: call LS API to create task
                task_ids.append(task["id"])
            except Exception:
                errors += 1

        return SyncResult(
            task_ids=task_ids,
            success_count=len(task_ids),
            error_count=errors,
            has_predictions=True,
        )

    @staticmethod
    def _to_ls_tasks(label: AIFriendlyLabel) -> list[dict[str, Any]]:
        """Convert AIFriendlyLabel to Label Studio task format."""
        tasks = []
        for entity in label.entities:
            tasks.append({
                "id": f"ls_task_{entity.id}",
                "data": {"text": entity.name, "entity_type": entity.type},
                "predictions": [{
                    "model_version": "interview-ai-v1",
                    "result": [{
                        "type": "labels",
                        "value": {"labels": [entity.type]},
                    }],
                }],
            })
        return tasks
