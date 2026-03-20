"""Unit tests for UserService."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.interview.auth_models import UserCreateRequest, UserUpdateRequest
from src.interview.user_service import UserService


@pytest.fixture
def user_service() -> UserService:
    return UserService()


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
            if isinstance(val, list):
                # list of rows for fetchall
                result.fetchall.return_value = val
                result.fetchone.return_value = val[0] if val else None
                result.scalar.return_value = val[0][0] if val and val[0] else 0
            else:
                result.fetchone.return_value = val
                result.scalar.return_value = val[0] if isinstance(val, tuple) else val
        else:
            result.fetchone.return_value = None
            result.fetchall.return_value = []
            result.scalar.return_value = 0
        return result

    mock_session.execute = AsyncMock(side_effect=_execute_side_effect)
    mock_session.commit = AsyncMock()

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = mock_session
    mock_ctx.__aexit__.return_value = False

    return mock_ctx, mock_session


_PATCH_TARGET = "src.interview.user_service.async_session_factory"
_NOW = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# list_users
# ---------------------------------------------------------------------------


class TestListUsers:
    """Tests for listing users with pagination and search."""

    @pytest.mark.asyncio
    async def test_list_users_basic(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        execute_results = [
            (2,),  # COUNT
            [(user_id, "a@corp.com", "member", True, _NOW)],  # SELECT rows
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = await user_service.list_users(tenant_id, page=1, size=20)

        assert result.total == 2
        assert result.page == 1
        assert result.size == 20
        assert len(result.items) == 1
        assert result.items[0].email == "a@corp.com"

    @pytest.mark.asyncio
    async def test_list_users_with_search(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())

        execute_results = [
            (0,),  # COUNT
            [],  # no rows
        ]
        mock_ctx, mock_session = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = await user_service.list_users(
                tenant_id, page=1, size=10, search="test"
            )

        assert result.total == 0
        assert result.items == []
        # Verify search param was passed
        calls = mock_session.execute.call_args_list
        assert len(calls) == 2


# ---------------------------------------------------------------------------
# create_user
# ---------------------------------------------------------------------------


class TestCreateUser:
    """Tests for creating a user."""

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        execute_results = [
            None,  # email uniqueness check (not found)
            (user_id, "new@corp.com", "member", True, _NOW),  # INSERT RETURNING
        ]
        mock_ctx, mock_session = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = await user_service.create_user(
                tenant_id,
                UserCreateRequest(email="new@corp.com", password="password123"),
            )

        assert result.id == user_id
        assert result.email == "new@corp.com"
        assert result.role == "member"
        assert result.is_active is True
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())

        execute_results = [
            (1,),  # email already exists
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            with pytest.raises(HTTPException) as exc_info:
                await user_service.create_user(
                    tenant_id,
                    UserCreateRequest(email="dup@corp.com", password="password123"),
                )

        assert exc_info.value.status_code == 400
        assert "已被注册" in exc_info.value.detail


# ---------------------------------------------------------------------------
# update_user
# ---------------------------------------------------------------------------


class TestUpdateUser:
    """Tests for updating a user."""

    @pytest.mark.asyncio
    async def test_update_user_role(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        execute_results = [
            (user_id,),  # verify user belongs to tenant
            None,  # UPDATE
            (user_id, "u@corp.com", "admin", True, _NOW),  # SELECT updated
        ]
        mock_ctx, mock_session = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = await user_service.update_user(
                tenant_id, user_id, UserUpdateRequest(role="admin")
            )

        assert result.role == "admin"
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_user_not_found(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        execute_results = [None]  # user not found
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            with pytest.raises(HTTPException) as exc_info:
                await user_service.update_user(
                    tenant_id, user_id, UserUpdateRequest(role="admin")
                )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# delete_user
# ---------------------------------------------------------------------------


class TestDeleteUser:
    """Tests for soft-deleting a user."""

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        execute_results = [
            (user_id,),  # verify user belongs to tenant
            None,  # UPDATE soft delete
        ]
        mock_ctx, mock_session = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            await user_service.delete_user(tenant_id, user_id)

        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_user_not_found(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        execute_results = [None]  # user not found
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            with pytest.raises(HTTPException) as exc_info:
                await user_service.delete_user(tenant_id, user_id)

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# batch_import
# ---------------------------------------------------------------------------


class TestBatchImport:
    """Tests for batch importing users."""

    @pytest.mark.asyncio
    async def test_batch_import_csv_success(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        csv_content = (
            "email,password,role\n"
            "user1@corp.com,password123,member\n"
            "user2@corp.com,password456,admin\n"
        ).encode("utf-8")

        # For each row: email uniqueness check (not found) + INSERT
        execute_results = [
            None,  # row 1 email check
            None,  # row 1 insert
            None,  # row 2 email check
            None,  # row 2 insert
        ]
        mock_ctx, mock_session = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = await user_service.batch_import(tenant_id, csv_content, "csv")

        assert result.success_count == 2
        assert result.failure_count == 0
        assert result.errors == []
        mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_import_invalid_email(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        csv_content = (
            "email,password,role\n"
            "not-an-email,password123,member\n"
        ).encode("utf-8")

        execute_results = []
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = await user_service.batch_import(tenant_id, csv_content, "csv")

        assert result.success_count == 0
        assert result.failure_count == 1
        assert result.errors[0].reason == "邮箱格式无效"

    @pytest.mark.asyncio
    async def test_batch_import_short_password(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        csv_content = (
            "email,password\n"
            "user@corp.com,short\n"
        ).encode("utf-8")

        execute_results = []
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = await user_service.batch_import(tenant_id, csv_content, "csv")

        assert result.success_count == 0
        assert result.failure_count == 1
        assert "密码" in result.errors[0].reason

    @pytest.mark.asyncio
    async def test_batch_import_duplicate_email(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        csv_content = (
            "email,password\n"
            "existing@corp.com,password123\n"
        ).encode("utf-8")

        execute_results = [
            (1,),  # email already exists
        ]
        mock_ctx, _ = _mock_session_factory(execute_results)

        with patch(_PATCH_TARGET, return_value=mock_ctx):
            result = await user_service.batch_import(tenant_id, csv_content, "csv")

        assert result.success_count == 0
        assert result.failure_count == 1
        assert "邮箱已存在" in result.errors[0].reason

    @pytest.mark.asyncio
    async def test_batch_import_exceeds_max_rows(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())
        # Build CSV with 501 data rows
        lines = ["email,password"]
        for i in range(501):
            lines.append(f"user{i}@corp.com,password123")
        csv_content = "\n".join(lines).encode("utf-8")

        with patch(_PATCH_TARGET):
            result = await user_service.batch_import(tenant_id, csv_content, "csv")

        assert result.success_count == 0
        assert "超过限制" in result.errors[0].reason

    @pytest.mark.asyncio
    async def test_batch_import_unsupported_type(self, user_service: UserService):
        tenant_id = str(uuid.uuid4())

        result = await user_service.batch_import(tenant_id, b"data", "txt")

        assert result.success_count == 0
        assert "不支持" in result.errors[0].reason
