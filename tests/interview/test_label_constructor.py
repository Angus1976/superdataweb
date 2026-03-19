"""Tests for LabelConstructor — parse, format, validate, generate."""

import pytest

from src.interview.label_constructor import LabelConstructor
from src.interview.models import (
    AIFriendlyLabel,
    Entity,
    ExtractionResult,
    Relation,
    Rule,
)


@pytest.fixture()
def lc() -> LabelConstructor:
    return LabelConstructor()


class TestParseFormat:
    def test_roundtrip(self, lc):
        label = AIFriendlyLabel(
            entities=[Entity(id="e1", name="A", type="t")],
            rules=[Rule(id="R1", name="r", condition="c", action="a")],
            relations=[Relation(id="rel1", source_entity="e1", target_entity="e2", relation_type="has")],
        )
        json_str = lc.format(label)
        parsed = lc.parse(json_str)
        reparsed = lc.parse(lc.format(parsed))
        assert reparsed == parsed

    def test_parse_empty_label(self, lc):
        label = lc.parse('{"entities":[],"rules":[],"relations":[]}')
        assert label.entities == []

    def test_format_produces_valid_json(self, lc):
        import json
        label = AIFriendlyLabel()
        result = json.loads(lc.format(label))
        assert "entities" in result


class TestValidate:
    def test_valid_label(self, lc):
        label = AIFriendlyLabel()
        result = lc.validate(label)
        assert result.is_valid is True

    def test_label_has_required_fields(self, lc):
        label = AIFriendlyLabel(
            entities=[Entity(id="e1", name="A", type="t")],
        )
        result = lc.validate(label)
        assert result.is_valid is True


class TestGenerateLabels:
    def test_generates_from_extractions(self, lc):
        results = [
            ExtractionResult(
                entities=[Entity(id="e1", name="A", type="t")],
                rules=[Rule(id="R1", name="r", condition="c", action="a")],
            ),
            ExtractionResult(
                entities=[Entity(id="e2", name="B", type="t")],
                relations=[Relation(id="rel1", source_entity="e1", target_entity="e2", relation_type="has")],
            ),
        ]
        label = lc.generate_labels("p1", results)
        assert len(label.entities) == 2
        assert len(label.rules) == 1
        assert len(label.relations) == 1

    def test_deduplicates_by_id(self, lc):
        results = [
            ExtractionResult(entities=[Entity(id="e1", name="A", type="t")]),
            ExtractionResult(entities=[Entity(id="e1", name="A", type="t")]),
        ]
        label = lc.generate_labels("p1", results)
        assert len(label.entities) == 1

    def test_empty_extractions(self, lc):
        label = lc.generate_labels("p1", [])
        assert label.entities == []
        assert label.rules == []
        assert label.relations == []
