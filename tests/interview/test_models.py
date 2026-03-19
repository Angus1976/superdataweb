"""Tests for Pydantic data models."""

import pytest
from pydantic import ValidationError

from src.interview.models import (
    AIFriendlyLabel,
    Entity,
    EntityAttribute,
    ExtractionResult,
    IndustryTemplateRequest,
    ProjectCreateRequest,
    Relation,
    Rule,
    ValidationResult,
)


class TestEntity:
    def test_valid_entity(self):
        e = Entity(id="e1", name="订单", type="核心实体")
        assert e.id == "e1"
        assert e.attributes == []

    def test_entity_with_attributes(self):
        attr = EntityAttribute(name="状态", type="枚举", values=["待支付", "已发货"])
        e = Entity(id="e1", name="订单", type="核心实体", attributes=[attr])
        assert len(e.attributes) == 1
        assert e.attributes[0].values == ["待支付", "已发货"]

    def test_entity_empty_id_rejected(self):
        with pytest.raises(ValidationError):
            Entity(id="", name="订单", type="核心实体")


class TestRule:
    def test_valid_rule(self):
        r = Rule(id="R001", name="金额审批", condition="金额>10000", action="经理审批")
        assert r.priority == "medium"
        assert r.related_entities == []

    def test_rule_empty_condition_rejected(self):
        with pytest.raises(ValidationError):
            Rule(id="R001", name="test", condition="", action="act")


class TestRelation:
    def test_valid_relation(self):
        r = Relation(id="rel1", source_entity="e1", target_entity="e2", relation_type="belongs_to")
        assert r.attributes == {}


class TestAIFriendlyLabel:
    def test_empty_label(self):
        label = AIFriendlyLabel()
        assert label.entities == []
        assert label.rules == []
        assert label.relations == []

    def test_roundtrip_json(self):
        label = AIFriendlyLabel(
            entities=[Entity(id="e1", name="订单", type="核心实体")],
            rules=[Rule(id="R1", name="规则1", condition="c", action="a")],
            relations=[Relation(id="r1", source_entity="e1", target_entity="e2", relation_type="has")],
        )
        json_str = label.model_dump_json()
        parsed = AIFriendlyLabel.model_validate_json(json_str)
        assert parsed == label

    def test_has_three_top_level_fields(self):
        label = AIFriendlyLabel()
        data = label.model_dump()
        assert "entities" in data
        assert "rules" in data
        assert "relations" in data


class TestProjectCreateRequest:
    def test_valid_request(self):
        req = ProjectCreateRequest(name="测试项目", industry="finance")
        assert req.business_domain is None

    def test_invalid_industry_rejected(self):
        with pytest.raises(ValidationError):
            ProjectCreateRequest(name="测试", industry="invalid")

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            ProjectCreateRequest(name="", industry="finance")

    def test_name_max_length(self):
        with pytest.raises(ValidationError):
            ProjectCreateRequest(name="x" * 256, industry="finance")

    def test_all_valid_industries(self):
        for ind in ("finance", "ecommerce", "manufacturing"):
            req = ProjectCreateRequest(name="p", industry=ind)
            assert req.industry == ind


class TestExtractionResult:
    def test_default_confidence(self):
        r = ExtractionResult()
        assert r.confidence == 0.0
        assert r.entities == []


class TestIndustryTemplateRequest:
    def test_valid_template(self):
        t = IndustryTemplateRequest(name="金融模板", industry="finance", system_prompt="你是专家")
        assert t.config == {}

    def test_empty_name_rejected(self):
        with pytest.raises(ValidationError):
            IndustryTemplateRequest(name="", industry="finance", system_prompt="prompt")


class TestValidationResult:
    def test_valid_result(self):
        v = ValidationResult(is_valid=True)
        assert v.errors == []

    def test_invalid_result(self):
        v = ValidationResult(is_valid=False, errors=["missing field"])
        assert len(v.errors) == 1
