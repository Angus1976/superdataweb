"""Tests for QualityAssessor — Ragas-based label quality evaluation."""

import pytest

from src.interview.quality_assessor import QualityAssessor, QualityReport
from src.interview.models import AIFriendlyLabel, Entity, Relation, Rule


@pytest.fixture()
def assessor() -> QualityAssessor:
    return QualityAssessor()


@pytest.fixture()
def rich_label() -> AIFriendlyLabel:
    return AIFriendlyLabel(
        entities=[Entity(id=f"e{i}", name=f"E{i}", type="t") for i in range(5)],
        rules=[Rule(id=f"R{i}", name=f"r{i}", condition="c", action="a") for i in range(3)],
        relations=[Relation(id=f"rel{i}", source_entity="e0", target_entity=f"e{i+1}", relation_type="has") for i in range(2)],
    )


class TestAssess:
    @pytest.mark.asyncio
    async def test_returns_quality_report(self, assessor, rich_label):
        report = await assessor.assess(rich_label)
        assert isinstance(report, QualityReport)
        assert 0.0 <= report.overall_score <= 1.0

    @pytest.mark.asyncio
    async def test_dimension_scores_present(self, assessor, rich_label):
        report = await assessor.assess(rich_label)
        assert "completeness" in report.dimension_scores
        assert "consistency" in report.dimension_scores
        assert "accuracy" in report.dimension_scores

    @pytest.mark.asyncio
    async def test_empty_label_low_score(self, assessor):
        report = await assessor.assess(AIFriendlyLabel())
        assert report.overall_score == 0.0

    @pytest.mark.asyncio
    async def test_empty_label_suggestions(self, assessor):
        report = await assessor.assess(AIFriendlyLabel())
        assert len(report.suggestions) == 3

    @pytest.mark.asyncio
    async def test_partial_label_suggestions(self, assessor):
        label = AIFriendlyLabel(entities=[Entity(id="e1", name="A", type="t")])
        report = await assessor.assess(label)
        # Missing rules and relations
        assert any('规则' in s for s in report.suggestions)
        assert any('关系' in s for s in report.suggestions)

    @pytest.mark.asyncio
    async def test_rich_label_higher_score(self, assessor, rich_label):
        report = await assessor.assess(rich_label)
        empty_report = await assessor.assess(AIFriendlyLabel())
        assert report.overall_score > empty_report.overall_score
