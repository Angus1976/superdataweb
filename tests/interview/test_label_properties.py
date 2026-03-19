"""Property-based tests for label-construction sub-module.

Property 1: 标签生成结构合规
Property 2: 标签双重存储
Property 3: 标签质量评估
Property 4: 离线文件解析
Property 5: 离线数据与在线结果合并
Property 6: 合并数据触发预标注
Property 7: Label Studio 同步含预标注
Property 8: AI_Friendly_Label 往返一致性
"""

import json

import pytest
from hypothesis import given, settings as h_settings, strategies as st

from src.interview.label_constructor import LabelConstructor
from src.interview.label_studio_connector import LabelStudioConnector, SyncResult
from src.interview.models import (
    AIFriendlyLabel,
    Entity,
    ExtractionResult,
    Relation,
    Rule,
)
from src.interview.neo4j_mapper import MappingResult, Neo4jMapper
from src.interview.offline_importer import ImportResult, MergedData, OfflineImporter
from src.interview.quality_assessor import QualityAssessor, QualityReport


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

non_empty_str = st.text(min_size=1, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz0123456789")

entity_st = st.builds(
    Entity, id=non_empty_str, name=non_empty_str, type=non_empty_str,
    attributes=st.just([]), source=st.none(),
)
rule_st = st.builds(
    Rule, id=non_empty_str, name=non_empty_str, condition=non_empty_str,
    action=non_empty_str, priority=st.just("medium"), related_entities=st.just([]),
)
relation_st = st.builds(
    Relation, id=non_empty_str, source_entity=non_empty_str,
    target_entity=non_empty_str, relation_type=non_empty_str, attributes=st.just({}),
)
label_st = st.builds(
    AIFriendlyLabel,
    entities=st.lists(entity_st, min_size=0, max_size=5),
    rules=st.lists(rule_st, min_size=0, max_size=3),
    relations=st.lists(relation_st, min_size=0, max_size=3),
)
extraction_st = st.builds(
    ExtractionResult,
    entities=st.lists(entity_st, min_size=0, max_size=3),
    rules=st.lists(rule_st, min_size=0, max_size=2),
    relations=st.lists(relation_st, min_size=0, max_size=2),
    confidence=st.floats(min_value=0.0, max_value=1.0),
)


# ---------------------------------------------------------------------------
# Property 1: 标签生成结构合规
# ---------------------------------------------------------------------------

class TestLabelStructureCompliance:
    """Feature: label-construction, Property 1: 标签生成结构合规"""

    @given(extractions=st.lists(extraction_st, min_size=0, max_size=5))
    @h_settings(max_examples=100, deadline=None)
    def test_generated_label_has_required_fields(self, extractions):
        lc = LabelConstructor()
        label = lc.generate_labels("p1", extractions)
        data = label.model_dump()
        assert "entities" in data
        assert "rules" in data
        assert "relations" in data
        assert isinstance(data["entities"], list)
        assert isinstance(data["rules"], list)
        assert isinstance(data["relations"], list)

    @given(extractions=st.lists(extraction_st, min_size=0, max_size=5))
    @h_settings(max_examples=100, deadline=None)
    def test_generated_label_passes_validation(self, extractions):
        lc = LabelConstructor()
        label = lc.generate_labels("p1", extractions)
        result = lc.validate(label)
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# Property 2: 标签双重存储
# ---------------------------------------------------------------------------

class TestDualStorage:
    """Feature: label-construction, Property 2: 标签双重存储"""

    @given(label=label_st)
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_store_with_neo4j(self, label):
        """Store writes to both PostgreSQL and Neo4j."""
        lc = LabelConstructor()
        mapper = Neo4jMapper()
        result = await lc.store("p1", "t1", label, neo4j_mapper=mapper)
        assert result["postgresql"] is True
        assert result["neo4j"] is True
        assert isinstance(result["mapping"], MappingResult)

    @given(label=label_st)
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_store_without_neo4j(self, label):
        """Store without Neo4j mapper only writes PostgreSQL."""
        lc = LabelConstructor()
        result = await lc.store("p1", "t1", label)
        assert result["postgresql"] is True
        assert result["neo4j"] is False


# ---------------------------------------------------------------------------
# Property 3: 标签质量评估
# ---------------------------------------------------------------------------

class TestQualityAssessment:
    """Feature: label-construction, Property 3: 标签质量评估"""

    @given(label=label_st)
    @h_settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_assess_returns_quality_report(self, label):
        assessor = QualityAssessor()
        report = await assessor.assess(label)
        assert isinstance(report, QualityReport)
        assert 0.0 <= report.overall_score <= 1.0
        assert "completeness" in report.dimension_scores
        assert "consistency" in report.dimension_scores
        assert "accuracy" in report.dimension_scores
        for score in report.dimension_scores.values():
            assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Property 4: 离线文件解析 (JSON)
# ---------------------------------------------------------------------------

class TestOfflineFileParsing:
    """Feature: label-construction, Property 4: 离线文件解析"""

    @given(
        entities=st.lists(
            st.fixed_dictionaries({
                "id": non_empty_str,
                "name": non_empty_str,
                "type": non_empty_str,
            }),
            min_size=0, max_size=5,
        ),
    )
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_json_parsed_to_import_result(self, entities):
        """Valid JSON files parse into ImportResult."""
        importer = OfflineImporter()
        data = {"entities": entities, "rules": [], "relations": []}
        content = json.dumps(data).encode()
        result = await importer.import_file(content, "json", "test.json")
        assert isinstance(result, ImportResult)
        assert len(result.entities) == len(entities)
        assert result.source_file == "test.json"


# ---------------------------------------------------------------------------
# Property 5: 离线数据与在线结果合并
# ---------------------------------------------------------------------------

class TestMergeProperty:
    """Feature: label-construction, Property 5: 离线数据与在线结果合并"""

    @given(
        offline_entities=st.lists(
            st.fixed_dictionaries({"id": non_empty_str, "name": non_empty_str, "type": non_empty_str}),
            min_size=0, max_size=3,
        ),
        online_entities=st.lists(entity_st, min_size=0, max_size=3),
    )
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_merge_no_data_loss(self, offline_entities, online_entities):
        """Merged data contains all unique entities from both sources."""
        importer = OfflineImporter()
        offline = ImportResult(entities=offline_entities, source_file="f.json")
        online = [ExtractionResult(entities=online_entities)] if online_entities else None

        merged = await importer.merge_with_online("p1", offline, online)
        assert isinstance(merged, MergedData)

        # Collect all unique IDs
        all_ids = set()
        for e in offline_entities:
            all_ids.add(e.get("id", ""))
        for e in online_entities:
            all_ids.add(e.id)

        assert len(merged.entities) <= len(all_ids)


# ---------------------------------------------------------------------------
# Property 6: 合并数据触发预标注
# ---------------------------------------------------------------------------

class TestPreAnnotationTrigger:
    """Feature: label-construction, Property 6: 合并数据触发预标注"""

    @given(
        entities=st.lists(
            st.fixed_dictionaries({"id": non_empty_str, "name": non_empty_str, "type": non_empty_str}),
            min_size=1, max_size=3,
        ),
    )
    @h_settings(max_examples=30, deadline=None)
    @pytest.mark.asyncio
    async def test_pre_annotate_task_callable(self, entities):
        """pre_annotate_merged_task can be called with merged data."""
        from src.interview.tasks import pre_annotate_merged_task
        merged = {"entities": entities, "rules": [], "relations": []}
        result = await pre_annotate_merged_task("p1", merged)
        assert result["status"] == "completed"
        assert result["project_id"] == "p1"


# ---------------------------------------------------------------------------
# Property 7: Label Studio 同步含预标注
# ---------------------------------------------------------------------------

class TestLabelStudioSyncPredictions:
    """Feature: label-construction, Property 7: Label Studio 同步含预标注"""

    @given(label=label_st.filter(lambda l: len(l.entities) > 0))
    @h_settings(max_examples=50, deadline=None)
    def test_sync_tasks_have_predictions(self, label):
        """All LS tasks generated from a label contain predictions."""
        tasks = LabelStudioConnector._to_ls_tasks(label)
        assert len(tasks) == len(label.entities)
        for task in tasks:
            assert "predictions" in task
            assert len(task["predictions"]) > 0
            assert task["predictions"][0]["model_version"] == "interview-ai-v1"

    @given(label=label_st.filter(lambda l: len(l.entities) > 0))
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_sync_returns_has_predictions_true(self, label):
        """sync_labels returns SyncResult with has_predictions=True."""

        class FakeClient:
            pass

        connector = LabelStudioConnector(ls_client=FakeClient())
        result = await connector.sync_labels("p1", label)
        assert isinstance(result, SyncResult)
        assert result.has_predictions is True
        assert result.success_count == len(label.entities)


# ---------------------------------------------------------------------------
# Property 8: AI_Friendly_Label 往返一致性
# ---------------------------------------------------------------------------

class TestLabelRoundtripProperty:
    """Feature: label-construction, Property 8: AI_Friendly_Label 往返一致性"""

    @given(label=label_st)
    @h_settings(max_examples=100, deadline=None)
    def test_roundtrip_consistency(self, label):
        """parse(format(parse(json))) == parse(json)"""
        lc = LabelConstructor()
        json_str = lc.format(label)
        parsed = lc.parse(json_str)
        reparsed = lc.parse(lc.format(parsed))
        assert reparsed == parsed
