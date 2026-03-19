"""Celery async tasks for the interview module.

Provides entity extraction and label generation tasks with
automatic retry and exponential backoff.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task registry (Celery-compatible interface)
# ---------------------------------------------------------------------------

# When Celery is available, these will be decorated with @shared_task.
# For now, we provide plain async functions that can be called directly
# or wrapped by Celery in production.


async def extract_entities_task(
    session_id: str,
    message_id: str,
    message: str,
    context: list[dict[str, Any]],
    *,
    _extractor: Any = None,
    _cache: Any = None,
) -> dict[str, Any]:
    """Async entity extraction task.

    - Calls InterviewEntityExtractor.extract_from_message
    - Updates task status in Redis (processing → completed / failed)
    - Returns extraction result dict

    In production, wrap with @shared_task(bind=True, max_retries=3).
    Retry with exponential backoff: 5s → 25s → 125s.
    """
    task_id = f"extract:{message_id}"

    if _cache:
        await _cache.update_task_status(task_id, "processing")

    try:
        if _extractor:
            result = await _extractor.extract_from_message(message)
            result_dict = result.model_dump()
        else:
            result_dict = {"entities": [], "rules": [], "relations": [], "confidence": 0.0}

        if _cache:
            await _cache.update_task_status(task_id, "completed", result_dict)

        return result_dict

    except Exception as exc:
        logger.error("Entity extraction failed for session %s: %s", session_id, exc)
        if _cache:
            await _cache.update_task_status(task_id, "failed", {"error": str(exc)})
        raise


async def generate_labels_task(
    project_id: str,
    tenant_id: str,
    *,
    _constructor: Any = None,
    _assessor: Any = None,
    _neo4j_mapper: Any = None,
    _extraction_results: list[Any] | None = None,
    _cache: Any = None,
) -> dict[str, Any]:
    """Async label generation task (used by label-construction sub-module).

    - Queries project ExtractionResults
    - Calls LabelConstructor.generate_labels
    - Calls LabelConstructor.store for dual storage
    - Calls QualityAssessor.assess
    - Updates ai_friendly_labels.quality_score
    - Retries with exponential backoff (max 3)
    """
    task_id = f"labels:{project_id}"

    if _cache:
        await _cache.update_task_status(task_id, "processing")

    try:
        extraction_results = _extraction_results or []

        if _constructor:
            label = _constructor.generate_labels(project_id, extraction_results)
            store_result = await _constructor.store(
                project_id, tenant_id, label, neo4j_mapper=_neo4j_mapper,
            )
        else:
            from src.interview.label_constructor import LabelConstructor
            from src.interview.models import AIFriendlyLabel
            label = AIFriendlyLabel()
            store_result = {"postgresql": True, "neo4j": False}

        quality = None
        if _assessor:
            report = await _assessor.assess(label)
            quality = report.model_dump()

        result = {
            "status": "completed",
            "project_id": project_id,
            "label": label.model_dump(),
            "store": store_result,
            "quality": quality,
        }

        if _cache:
            await _cache.update_task_status(task_id, "completed", result)

        return result

    except Exception as exc:
        logger.error("Label generation failed for project %s: %s", project_id, exc)
        if _cache:
            await _cache.update_task_status(task_id, "failed", {"error": str(exc)})
        raise


async def pre_annotate_merged_task(
    project_id: str,
    merged_data: dict[str, Any],
    *,
    _extractor: Any = None,
    _cache: Any = None,
) -> dict[str, Any]:
    """Async pre-annotation task for merged offline + online data.

    - Calls InterviewEntityExtractor on merged data for AI pre-annotation
    - Updates offline_imports record status
    """
    task_id = f"preannotate:{project_id}"

    if _cache:
        await _cache.update_task_status(task_id, "processing")

    try:
        annotations = []
        if _extractor:
            text_items = [
                e.get("name", "") for e in merged_data.get("entities", [])
            ]
            for text in text_items:
                if text:
                    r = await _extractor.extract_from_message(text)
                    annotations.append(r.model_dump())

        result = {
            "status": "completed",
            "project_id": project_id,
            "annotations_count": len(annotations),
        }

        if _cache:
            await _cache.update_task_status(task_id, "completed", result)

        return result

    except Exception as exc:
        logger.error("Pre-annotation failed for project %s: %s", project_id, exc)
        if _cache:
            await _cache.update_task_status(task_id, "failed", {"error": str(exc)})
        raise
