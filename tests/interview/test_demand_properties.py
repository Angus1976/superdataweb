"""Property-based tests for demand-collection sub-module.

Property 1: 项目创建持久化
Property 2: 文档上传触发实体提取
Property 3: 标签生成结构合规
Property 4: 行业模板 CRUD
Property 5: 项目创建自动加载行业模板
Property 6: AI_Friendly_Label 往返一致性
"""

import json

import pytest
from hypothesis import given, settings as h_settings, strategies as st

from src.interview.models import (
    AIFriendlyLabel,
    Entity,
    EntityAttribute,
    ExtractionResult,
    ProjectCreateRequest,
    Relation,
    Rule,
    ValidationResult,
)
from src.interview.label_constructor import LabelConstructor
from src.interview.entity_extractor import InterviewEntityExtractor
from src.interview.system import InterviewSystem, reset_projects
from src.interview import templates as tmpl_store


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

non_empty_str = st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789_")
industry_st = st.sampled_from(["finance", "ecommerce", "manufacturing"])

entity_st = st.builds(
    Entity,
    id=non_empty_str,
    name=non_empty_str,
    type=non_empty_str,
    attributes=st.just([]),
    source=st.none(),
)

rule_st = st.builds(
    Rule,
    id=non_empty_str,
    name=non_empty_str,
    condition=non_empty_str,
    action=non_empty_str,
    priority=st.just("medium"),
    related_entities=st.just([]),
)

relation_st = st.builds(
    Relation,
    id=non_empty_str,
    source_entity=non_empty_str,
    target_entity=non_empty_str,
    relation_type=non_empty_str,
    attributes=st.just({}),
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
# Property 6: AI_Friendly_Label 往返一致性
# ---------------------------------------------------------------------------

class TestLabelRoundtrip:
    """Feature: demand-collection, Property 6: AI_Friendly_Label 往返一致性"""

    @given(label=label_st)
    @h_settings(max_examples=100, deadline=None)
    def test_parse_format_roundtrip(self, label):
        """parse(format(parse(json))) == parse(json)"""
        lc = LabelConstructor()
        json_str = lc.format(label)
        parsed = lc.parse(json_str)
        reparsed = lc.parse(lc.format(parsed))
        assert reparsed == parsed

    @given(label=label_st)
    @h_settings(max_examples=100, deadline=None)
    def test_format_produces_valid_json(self, label):
        lc = LabelConstructor()
        result = json.loads(lc.format(label))
        assert "entities" in result
        assert "rules" in result
        assert "relations" in result


# ---------------------------------------------------------------------------
# Property 3: 标签生成结构合规
# ---------------------------------------------------------------------------

class TestLabelStructureCompliance:
    """Feature: demand-collection, Property 3: 标签生成结构合规"""

    @given(label=label_st)
    @h_settings(max_examples=100, deadline=None)
    def test_label_has_three_top_level_fields(self, label):
        """AIFriendlyLabel must have entities, rules, relations."""
        data = label.model_dump()
        assert "entities" in data
        assert "rules" in data
        assert "relations" in data
        assert isinstance(data["entities"], list)
        assert isinstance(data["rules"], list)
        assert isinstance(data["relations"], list)

    @given(label=label_st)
    @h_settings(max_examples=100, deadline=None)
    def test_label_passes_validation(self, label):
        lc = LabelConstructor()
        result = lc.validate(label)
        assert result.is_valid is True


# ---------------------------------------------------------------------------
# Property 4: 行业模板 CRUD
# ---------------------------------------------------------------------------

class TestTemplateCRUDProperty:
    """Feature: demand-collection, Property 4: 行业模板 CRUD"""

    @given(
        name=non_empty_str,
        industry=industry_st,
        prompt=non_empty_str,
    )
    @h_settings(max_examples=50, deadline=None)
    def test_created_template_retrievable(self, name, industry, prompt):
        """Created template can be retrieved with consistent content."""
        from src.interview.models import IndustryTemplateRequest
        tmpl_store.reset_templates()
        req = IndustryTemplateRequest(name=name, industry=industry, system_prompt=prompt)
        created = tmpl_store.create_template(req)
        retrieved = tmpl_store.get_template(created.id)
        assert retrieved is not None
        assert retrieved.name == name
        assert retrieved.industry == industry
        assert retrieved.system_prompt == prompt


# ---------------------------------------------------------------------------
# Property 5: 项目创建自动加载行业模板
# ---------------------------------------------------------------------------

class TestProjectTemplateLoading:
    """Feature: demand-collection, Property 5: 项目创建自动加载行业模板"""

    @given(industry=industry_st)
    @h_settings(max_examples=30, deadline=None)
    def test_industry_template_exists(self, industry):
        """Each valid industry has a matching template."""
        tmpl_store.reset_templates()
        tmpl = tmpl_store.get_template_by_industry(industry)
        assert tmpl is not None
        assert tmpl.industry == industry


# ---------------------------------------------------------------------------
# Property 1: 项目创建持久化
# ---------------------------------------------------------------------------

class TestProjectCreation:
    """Feature: demand-collection, Property 1: 项目创建持久化"""

    @given(
        name=non_empty_str,
        industry=industry_st,
    )
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_project_persisted(self, name, industry):
        """Created project can be listed back."""
        reset_projects()
        system = InterviewSystem()
        req = ProjectCreateRequest(name=name, industry=industry)
        created = await system.create_project("tenant_test", req)
        projects = await system.list_projects("tenant_test")
        assert any(p.id == created.id for p in projects)
        match = next(p for p in projects if p.id == created.id)
        assert match.name == name
        assert match.industry == industry


# ---------------------------------------------------------------------------
# Property 2: 文档上传触发实体提取
# ---------------------------------------------------------------------------

class TestDocumentExtraction:
    """Feature: demand-collection, Property 2: 文档上传触发实体提取"""

    @given(message=st.text(min_size=1, max_size=200, alphabet="abcdefghijklmnopqrstuvwxyz "))
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_extract_returns_extraction_result(self, message):
        """Entity extractor always returns a valid ExtractionResult."""
        extractor = InterviewEntityExtractor()
        result = await extractor.extract_from_message(message)
        assert isinstance(result, ExtractionResult)
        assert isinstance(result.entities, list)
        assert isinstance(result.rules, list)
        assert isinstance(result.relations, list)
        assert 0.0 <= result.confidence <= 1.0
