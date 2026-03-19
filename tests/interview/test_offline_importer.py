"""Tests for OfflineImporter — file validation, parsing, and merge."""

import json

import pytest

from src.interview.offline_importer import (
    ImportResult,
    MergedData,
    OfflineImporter,
)
from src.interview.models import Entity, ExtractionResult, Rule


@pytest.fixture()
def importer() -> OfflineImporter:
    return OfflineImporter()


class TestValidateFile:
    def test_json_valid(self, importer):
        r = importer.validate_file("data.json", "json")
        assert r.is_valid is True

    def test_xlsx_valid(self, importer):
        r = importer.validate_file("data.xlsx", "xlsx")
        assert r.is_valid is True

    def test_unsupported_format(self, importer):
        r = importer.validate_file("data.csv", "csv")
        assert r.is_valid is False
        assert "Unsupported" in r.errors[0]


class TestImportJson:
    @pytest.mark.asyncio
    async def test_parse_valid_json(self, importer):
        data = {"entities": [{"id": "e1", "name": "A", "type": "t"}], "rules": [], "relations": []}
        content = json.dumps(data).encode()
        result = await importer.import_file(content, "json", "test.json")
        assert isinstance(result, ImportResult)
        assert len(result.entities) == 1
        assert result.source_file == "test.json"

    @pytest.mark.asyncio
    async def test_invalid_json(self, importer):
        with pytest.raises(ValueError, match="Invalid JSON"):
            await importer.import_file(b"not json", "json", "bad.json")

    @pytest.mark.asyncio
    async def test_json_root_not_object(self, importer):
        with pytest.raises(ValueError, match="root must be an object"):
            await importer.import_file(b"[1,2,3]", "json", "arr.json")

    @pytest.mark.asyncio
    async def test_unsupported_type_raises(self, importer):
        with pytest.raises(ValueError, match="Unsupported"):
            await importer.import_file(b"", "csv", "data.csv")


class TestMergeWithOnline:
    @pytest.mark.asyncio
    async def test_merge_deduplicates(self, importer):
        offline = ImportResult(
            entities=[{"id": "e1", "name": "A", "type": "t"}],
            source_file="f.json",
        )
        online = [
            ExtractionResult(entities=[Entity(id="e1", name="A", type="t")]),
        ]
        merged = await importer.merge_with_online("p1", offline, online)
        assert isinstance(merged, MergedData)
        assert len(merged.entities) == 1

    @pytest.mark.asyncio
    async def test_merge_combines_unique(self, importer):
        offline = ImportResult(
            entities=[{"id": "e2", "name": "B", "type": "t"}],
            source_file="f.json",
        )
        online = [
            ExtractionResult(entities=[Entity(id="e1", name="A", type="t")]),
        ]
        merged = await importer.merge_with_online("p1", offline, online)
        assert len(merged.entities) == 2

    @pytest.mark.asyncio
    async def test_merge_no_online(self, importer):
        offline = ImportResult(
            entities=[{"id": "e1", "name": "A", "type": "t"}],
            rules=[{"id": "R1", "name": "r", "condition": "c", "action": "a"}],
            source_file="f.json",
        )
        merged = await importer.merge_with_online("p1", offline)
        assert len(merged.entities) == 1
        assert len(merged.rules) == 1
        assert merged.online_count == 0
