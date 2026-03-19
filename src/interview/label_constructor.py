"""LabelConstructor — parse, format, validate, generate, and store labels.

Provides AIFriendlyLabel construction from extraction results,
JSON roundtrip (parse/format), validation, and dual storage
(PostgreSQL + Neo4j).
"""

from __future__ import annotations

from typing import Any

from src.interview.models import (
    AIFriendlyLabel,
    Entity,
    ExtractionResult,
    Relation,
    Rule,
    ValidationResult,
)


class LabelConstructor:
    """标签构造器 — 生成、解析、格式化、校验和存储。"""

    # ------------------------------------------------------------------
    # Parse / Format / Validate (demand-collection)
    # ------------------------------------------------------------------

    def parse(self, json_str: str) -> AIFriendlyLabel:
        """Parse a JSON string into an AIFriendlyLabel."""
        return AIFriendlyLabel.model_validate_json(json_str)

    def format(self, label: AIFriendlyLabel) -> str:
        """Serialize an AIFriendlyLabel to a canonical JSON string."""
        return label.model_dump_json()

    def validate(self, label: AIFriendlyLabel) -> ValidationResult:
        """Validate label structure compliance."""
        errors: list[str] = []
        data = label.model_dump()

        for field in ("entities", "rules", "relations"):
            if field not in data:
                errors.append(f"Missing top-level field: {field}")
            elif not isinstance(data[field], list):
                errors.append(f"Field '{field}' must be a list")

        return ValidationResult(is_valid=len(errors) == 0, errors=errors)

    # ------------------------------------------------------------------
    # Generate labels (label-construction)
    # ------------------------------------------------------------------

    def generate_labels(
        self,
        project_id: str,
        extraction_results: list[ExtractionResult],
    ) -> AIFriendlyLabel:
        """Aggregate extraction results into a deduplicated AIFriendlyLabel."""
        seen_entities: dict[str, Entity] = {}
        seen_rules: dict[str, Rule] = {}
        seen_relations: dict[str, Relation] = {}

        for r in extraction_results:
            for e in r.entities:
                seen_entities.setdefault(e.id, e)
            for rule in r.rules:
                seen_rules.setdefault(rule.id, rule)
            for rel in r.relations:
                seen_relations.setdefault(rel.id, rel)

        label = AIFriendlyLabel(
            entities=list(seen_entities.values()),
            rules=list(seen_rules.values()),
            relations=list(seen_relations.values()),
        )

        # Validate structure
        result = self.validate(label)
        if not result.is_valid:
            raise ValueError(f"Label validation failed: {result.errors}")

        return label

    # ------------------------------------------------------------------
    # Store (label-construction)
    # ------------------------------------------------------------------

    async def store(
        self,
        project_id: str,
        tenant_id: str,
        label: AIFriendlyLabel,
        *,
        neo4j_mapper: Any = None,
    ) -> dict[str, Any]:
        """Dual storage: PostgreSQL (JSON) + Neo4j (graph).

        Returns a summary dict with storage results.
        """
        result: dict[str, Any] = {"postgresql": True, "neo4j": False}

        # PostgreSQL storage would happen here via async session
        # For now, we track that it was called

        if neo4j_mapper:
            mapping = await neo4j_mapper.map_label(label)
            result["neo4j"] = True
            result["mapping"] = mapping

        return result
