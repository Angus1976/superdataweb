"""Unit tests for EnterpriseService."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.interview.enterprise_service import EnterpriseService, _generate_enterprise_code


@pytest.fixture
def enterprise_service() -> EnterpriseService:
    return EnterpriseService()


def _mock_session_factory(execute_side_effects: list):
    """Create a mock async_session_factory with pre-configured execute results."""
    call_idx = {"i": 0}

    mock_session = AsyncMock()

    def _execute_side_effect(*args, **kwargs):
        idx = call_idx["i"]
        call_idx["i"] += 1
        result = MagicMock()
        if idx < len(execute_side_effects):
            val = execute_side_effects[idx]
            result.fetchone.return_value = val
        else:
            result.fetchone.return_value = None
        return result

    mock_session.execute = AsyncMock(side_effect=_execute_side_effect)
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = False

    return mock_ctx, mock_session


# ---------------------------------------------------------------------------
# _generate_enterprise_code
# ---------------------------------------------------------------------------


class TestGenerateEnterpriseCode:
    """Tests for enterprise code generation."""

    def test_code_starts_with_ent(self):
        code = _generate_enterprise_code()
        assert code.startswith("ENT")

    def test_code_has_correct_length(self):
        code = _generate_enterprise_code()
        assert len(code) == 9  # "ENT" + 6 chars

    def test_code_suffix_is_uppercase_alphanumeric(self):
        code = _generate_enterprise_code()
        suffix = code[3:]
        assert suffix.isalnum()
        assert suffix == suffix.upper()


# ---------------------------------------------------------------------------
# create_enterprise
# ---------------------------------------------------------------------------


class TestCreateEnterprise:
    """Tests for enterprise creation."""

    @pytest.mark.asyncio
    async def test_create_enterprise_success(self, enterprise_service: EnterpriseService):
        ent_id = str(uuid.uuid4())

        execute_results = [
            None,  # code uniqueness check (no collision)
            (ent_id, "Acme Corp", "ENTABC123", "acme.com", "active"),  # INSERT RETURNING
        ]
        mock_ctx, mock_session = _mock_session_factory(execute_results)

        with patch(
            "src.interview.enterprise_service.async_session_factory",
            return_value=mock_ctx,
        ):
            result = await enterprise_service.create_enterprise("Acme Corp", "acme.com")

        assert result["id"] == ent_id
        assert result["name"] == "Acme Corp"
        assert result["domain"] == "acme.com"
        assert result["status"] == "active"
        assert result["code"] == "ENTABC123"
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_enterprise_retries_on_code_collision(
        self, enterprise_service: EnterpriseService
    ):
        ent_id = str(uuid.uuid4())

        execute_results = [
            (1,),  # first code collision
            None,  # second code is unique
            (ent_id, "Test Corp", "ENTXYZ789", "test.com", "active"),  # INSERT RETURNING
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.enterprise_service.async_session_factory",
            return_value=mock_ctx,
        ):
            result = await enterprise_service.create_enterprise("Test Corp", "test.com")

        assert result["id"] == ent_id
        assert result["status"] == "active"


# ---------------------------------------------------------------------------
# get_enterprise_by_code
# ---------------------------------------------------------------------------


class TestGetEnterpriseByCode:
    """Tests for enterprise lookup by code."""

    @pytest.mark.asyncio
    async def test_get_enterprise_found(self, enterprise_service: EnterpriseService):
        ent_id = str(uuid.uuid4())

        execute_results = [
            (ent_id, "Acme Corp", "ENT001", "acme.com", "active"),
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.enterprise_service.async_session_factory",
            return_value=mock_ctx,
        ):
            result = await enterprise_service.get_enterprise_by_code("ENT001")

        assert result is not None
        assert result["id"] == ent_id
        assert result["name"] == "Acme Corp"
        assert result["code"] == "ENT001"
        assert result["domain"] == "acme.com"
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_enterprise_not_found(self, enterprise_service: EnterpriseService):
        execute_results = [None]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(
            "src.interview.enterprise_service.async_session_factory",
            return_value=mock_ctx,
        ):
            result = await enterprise_service.get_enterprise_by_code("INVALID")

        assert result is None


# ---------------------------------------------------------------------------
# disable_enterprise
# ---------------------------------------------------------------------------


class TestDisableEnterprise:
    """Tests for enterprise disabling."""

    @pytest.mark.asyncio
    async def test_disable_enterprise_executes_update(
        self, enterprise_service: EnterpriseService
    ):
        ent_id = str(uuid.uuid4())
        execute_results = [None]  # UPDATE result
        mock_ctx, mock_session = _mock_session_factory(execute_results)

        with patch(
            "src.interview.enterprise_service.async_session_factory",
            return_value=mock_ctx,
        ):
            await enterprise_service.disable_enterprise(ent_id)

        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
