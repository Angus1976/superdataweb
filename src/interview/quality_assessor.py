"""QualityAssessor — Ragas-based label quality evaluation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.interview.models import AIFriendlyLabel


class QualityReport(BaseModel):
    """质量评估报告。"""
    overall_score: float
    dimension_scores: dict[str, float] = {}
    suggestions: list[str] = []


class QualityAssessor:
    """复用现有 quality_monitoring/ 模块的 Ragas 框架。"""

    def __init__(self, ragas_evaluator: Any = None) -> None:
        self._evaluator = ragas_evaluator

    async def assess(
        self, label: AIFriendlyLabel, context: dict[str, Any] | None = None
    ) -> QualityReport:
        """Evaluate label quality using Ragas framework."""
        if self._evaluator:
            return await self._evaluator.evaluate(label, context)

        # Stub: compute basic quality metrics
        entity_count = len(label.entities)
        rule_count = len(label.rules)
        relation_count = len(label.relations)
        total = entity_count + rule_count + relation_count

        completeness = min(1.0, total / 10) if total > 0 else 0.0
        consistency = 1.0 if total > 0 else 0.0
        accuracy = 0.85 if total > 0 else 0.0

        overall = round((completeness + consistency + accuracy) / 3, 4)

        suggestions = []
        if entity_count == 0:
            suggestions.append("建议添加业务实体")
        if rule_count == 0:
            suggestions.append("建议添加业务规则")
        if relation_count == 0:
            suggestions.append("建议添加实体关系")

        return QualityReport(
            overall_score=overall,
            dimension_scores={
                "completeness": completeness,
                "consistency": consistency,
                "accuracy": accuracy,
            },
            suggestions=suggestions,
        )
