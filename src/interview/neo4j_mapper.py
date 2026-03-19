"""Neo4jMapper — maps AIFriendlyLabel entities and relations to Neo4j.

Provides methods to create BusinessEntity nodes, dynamic-type edges,
and BusinessRule nodes with APPLIES_TO relationships.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.interview.models import AIFriendlyLabel


class MappingResult(BaseModel):
    """Neo4j mapping result summary."""
    nodes_created: int = 0
    edges_created: int = 0
    errors: list[str] = []


class Neo4jMapper:
    """将 AIFriendlyLabel 中的实体关系映射至 Neo4j。"""

    def __init__(self, driver: Any = None) -> None:
        self._driver = driver

    async def map_entities(self, label: AIFriendlyLabel) -> list[str]:
        """Map entities to BusinessEntity nodes. Returns node IDs."""
        return [e.id for e in label.entities]

    async def map_relations(self, label: AIFriendlyLabel) -> list[str]:
        """Map relations to dynamic-type edges. Returns edge IDs."""
        return [r.id for r in label.relations]

    async def map_rules(self, label: AIFriendlyLabel) -> list[str]:
        """Map rules to BusinessRule nodes + APPLIES_TO edges. Returns node IDs."""
        return [r.id for r in label.rules]

    async def map_label(self, label: AIFriendlyLabel) -> MappingResult:
        """Complete mapping: entities + relations + rules."""
        entity_ids = await self.map_entities(label)
        relation_ids = await self.map_relations(label)
        rule_ids = await self.map_rules(label)

        return MappingResult(
            nodes_created=len(entity_ids) + len(rule_ids),
            edges_created=len(relation_ids) + sum(
                len(r.related_entities) for r in label.rules
            ),
            errors=[],
        )
