"""Tests for InterviewEntityExtractor."""

import pytest

from src.interview.entity_extractor import InterviewEntityExtractor, SUPPORTED_FILE_TYPES
from src.interview.models import Entity, ExtractionResult, Rule, Relation


@pytest.fixture()
def extractor() -> InterviewEntityExtractor:
    return InterviewEntityExtractor()


class TestSupportedTypes:
    def test_supported_types(self):
        assert SUPPORTED_FILE_TYPES == {"docx", "xlsx", "pdf"}


class TestExtractFromDocument:
    @pytest.mark.asyncio
    async def test_unsupported_type_raises(self, extractor):
        with pytest.raises(ValueError, match="Unsupported file type"):
            await extractor.extract_from_document(b"data", "txt")


class TestExtractFromMessage:
    @pytest.mark.asyncio
    async def test_returns_extraction_result(self, extractor):
        result = await extractor.extract_from_message("测试消息")
        assert isinstance(result, ExtractionResult)


class TestMergeExtractions:
    @pytest.mark.asyncio
    async def test_merge_deduplicates_by_id(self, extractor):
        r1 = ExtractionResult(
            entities=[Entity(id="e1", name="A", type="t")],
            rules=[Rule(id="R1", name="r", condition="c", action="a")],
            confidence=0.8,
        )
        r2 = ExtractionResult(
            entities=[Entity(id="e1", name="A", type="t"), Entity(id="e2", name="B", type="t")],
            rules=[Rule(id="R1", name="r", condition="c", action="a")],
            confidence=0.6,
        )
        merged = await extractor.merge_extractions([r1, r2])
        assert len(merged.entities) == 2
        assert len(merged.rules) == 1

    @pytest.mark.asyncio
    async def test_merge_empty_list(self, extractor):
        merged = await extractor.merge_extractions([])
        assert merged.entities == []
        assert merged.confidence == 0.0

    @pytest.mark.asyncio
    async def test_merge_averages_confidence(self, extractor):
        r1 = ExtractionResult(confidence=0.8)
        r2 = ExtractionResult(confidence=0.6)
        merged = await extractor.merge_extractions([r1, r2])
        assert merged.confidence == 0.7

    @pytest.mark.asyncio
    async def test_merge_preserves_relations(self, extractor):
        r1 = ExtractionResult(
            relations=[Relation(id="rel1", source_entity="e1", target_entity="e2", relation_type="has")]
        )
        r2 = ExtractionResult(
            relations=[Relation(id="rel2", source_entity="e3", target_entity="e4", relation_type="owns")]
        )
        merged = await extractor.merge_extractions([r1, r2])
        assert len(merged.relations) == 2
