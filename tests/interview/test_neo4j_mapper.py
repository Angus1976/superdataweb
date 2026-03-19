"""Tests for Neo4jMapper — entity/relation/rule mapping to Neo4j."""

import pytest

from src.interview.neo4j_mapper import MappingResult, Neo4jMapper
from src.interview.models import AIFriendlyLabel, Entity, Relation, Rule


@pytest.fixture()
def mapper() -> Neo4jMapper:
    return Neo4jMapper()


@pytest.fixture()
def sample_label() -> AIFriendlyLabel:
    return AIFriendlyLabel(
        entities=[
            Entity(id="e1", name="Customer", type="person"),
            Entity(id="e2", name="Order", type="object"),
        ],
        rules=[
            Rule(id="R1", name="discount", condition="amount>100", action="apply_10pct", related_entities=["e1"]),
        ],
        relations=[
            Relation(id="rel1", source_entity="e1", target_entity="e2", relation_type="places"),
        ],
    )


class TestMapEntities:
    @pytest.mark.asyncio
    async def test_returns_entity_ids(self, mapper, sample_label):
        ids = await mapper.map_entities(sample_label)
        assert ids == ["e1", "e2"]

    @pytest.mark.asyncio
    async def test_empty_entities(self, mapper):
        ids = await mapper.map_entities(AIFriendlyLabel())
        assert ids == []


class TestMapRelations:
    @pytest.mark.asyncio
    async def test_returns_relation_ids(self, mapper, sample_label):
        ids = await mapper.map_relations(sample_label)
        assert ids == ["rel1"]

    @pytest.mark.asyncio
    async def test_empty_relations(self, mapper):
        ids = await mapper.map_relations(AIFriendlyLabel())
        assert ids == []


class TestMapRules:
    @pytest.mark.asyncio
    async def test_returns_rule_ids(self, mapper, sample_label):
        ids = await mapper.map_rules(sample_label)
        assert ids == ["R1"]

    @pytest.mark.asyncio
    async def test_empty_rules(self, mapper):
        ids = await mapper.map_rules(AIFriendlyLabel())
        assert ids == []


class TestMapLabel:
    @pytest.mark.asyncio
    async def test_full_mapping(self, mapper, sample_label):
        result = await mapper.map_label(sample_label)
        assert isinstance(result, MappingResult)
        # 2 entities + 1 rule = 3 nodes
        assert result.nodes_created == 3
        # 1 relation + 1 APPLIES_TO (R1 has 1 related_entity) = 2 edges
        assert result.edges_created == 2
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_empty_label(self, mapper):
        result = await mapper.map_label(AIFriendlyLabel())
        assert result.nodes_created == 0
        assert result.edges_created == 0
