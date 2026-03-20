"""Tests for SessionManager LLM integration — send_message() with LLMClient.

Validates Requirements 7.1, 7.2, 7.3, 7.4, 7.5
"""

import pytest
from unittest.mock import AsyncMock, patch

from src.interview.models import ProjectCreateRequest
from src.interview.session_cache import SessionCache
from src.interview.session_models import AIResponse
from src.interview.system import (
    InterviewSystem,
    SessionManager,
    reset_projects,
    reset_sessions,
)
from src.interview.llm_client import LLMClient
from src.interview.llm_config_service import LLMConfigService
from src.interview.llm_models import LLMNotConfiguredError, LLMServiceError
from src.interview.prompt_manager import PromptManager
from src.interview import templates as tmpl_store


@pytest.fixture(autouse=True)
def _reset():
    reset_projects()
    reset_sessions()
    tmpl_store.reset_templates()
    yield
    reset_projects()
    reset_sessions()
    tmpl_store.reset_templates()


@pytest.fixture()
def cache() -> SessionCache:
    return SessionCache()


@pytest.fixture()
def system() -> InterviewSystem:
    return InterviewSystem()


@pytest.fixture()
def mock_llm_client() -> LLMClient:
    """Create a mock LLMClient with chat_completion as AsyncMock."""
    client = AsyncMock(spec=LLMClient)
    client.chat_completion = AsyncMock(return_value="这是来自 LLM 的真实回复")
    # Keep build_messages as the real static method
    client.build_messages = LLMClient.build_messages
    return client


@pytest.fixture()
def prompt_manager() -> PromptManager:
    return PromptManager()


async def _create_session(system, mgr, tenant_id="t1", industry="finance"):
    """Helper to create a project and start a session."""
    proj = await system.create_project(
        tenant_id, ProjectCreateRequest(name="P", industry=industry)
    )
    session = await mgr.start_session(proj.id, tenant_id)
    return session


class TestSendMessageWithLLMClient:
    """Tests for send_message() when LLMClient is injected."""

    @pytest.mark.asyncio
    async def test_calls_llm_client(self, system, cache, mock_llm_client, prompt_manager):
        """Validates: Requirement 7.1 — calls LLMClient instead of stub."""
        mgr = SessionManager(
            cache=cache, llm_client=mock_llm_client, prompt_manager=prompt_manager,
        )
        session = await _create_session(system, mgr)
        resp = await mgr.send_message(session.session_id, "t1", "我们需要订单管理")

        assert isinstance(resp, AIResponse)
        assert resp.message == "这是来自 LLM 的真实回复"
        mock_llm_client.chat_completion.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_builds_correct_message_list(self, system, cache, mock_llm_client, prompt_manager):
        """Validates: Requirement 7.2 — message list: system + history + user."""
        mgr = SessionManager(
            cache=cache, llm_client=mock_llm_client, prompt_manager=prompt_manager,
        )
        session = await _create_session(system, mgr)

        # First message
        await mgr.send_message(session.session_id, "t1", "第一条消息")
        # Second message — history should include first exchange
        await mgr.send_message(session.session_id, "t1", "第二条消息")

        # Check the second call's messages argument
        call_args = mock_llm_client.chat_completion.call_args_list[1]
        messages = call_args[0][1]  # positional arg: messages

        # First message should be system
        assert messages[0]["role"] == "system"
        # Last message should be user with current content
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "第二条消息"
        # Total: system + 2 history (user+assistant from round 1) + current user
        assert len(messages) == 4

    @pytest.mark.asyncio
    async def test_system_prompt_from_template(self, system, cache, mock_llm_client, prompt_manager):
        """Validates: Requirement 7.3 — system prompt loaded from template."""
        mgr = SessionManager(
            cache=cache, llm_client=mock_llm_client, prompt_manager=prompt_manager,
        )
        session = await _create_session(system, mgr, industry="finance")

        await mgr.send_message(session.session_id, "t1", "测试消息")

        call_args = mock_llm_client.chat_completion.call_args
        messages = call_args[0][1]
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        # Should contain the finance template's system_prompt
        assert "金融" in system_msg["content"]


class TestSendMessageErrorHandling:
    """Tests for error handling in send_message() with LLMClient."""

    @pytest.mark.asyncio
    async def test_llm_not_configured_returns_friendly_message(
        self, system, cache, prompt_manager,
    ):
        """Validates: Requirement 7.4 — LLMNotConfiguredError → friendly message."""
        mock_client = AsyncMock(spec=LLMClient)
        mock_client.chat_completion = AsyncMock(
            side_effect=LLMNotConfiguredError()
        )
        mock_client.build_messages = LLMClient.build_messages

        mgr = SessionManager(
            cache=cache, llm_client=mock_client, prompt_manager=prompt_manager,
        )
        session = await _create_session(system, mgr)
        resp = await mgr.send_message(session.session_id, "t1", "你好")

        assert resp.message == "AI 服务尚未配置，请联系管理员完成 LLM 设置"
        assert resp.current_round == 1  # round still increments

    @pytest.mark.asyncio
    async def test_llm_service_error_returns_unavailable_message(
        self, system, cache, prompt_manager,
    ):
        """Validates: Requirement 7.5 — LLMServiceError → unavailable message + log."""
        mock_client = AsyncMock(spec=LLMClient)
        mock_client.chat_completion = AsyncMock(
            side_effect=LLMServiceError(status_code=500, message="Internal error")
        )
        mock_client.build_messages = LLMClient.build_messages

        mgr = SessionManager(
            cache=cache, llm_client=mock_client, prompt_manager=prompt_manager,
        )
        session = await _create_session(system, mgr)
        resp = await mgr.send_message(session.session_id, "t1", "你好")

        assert resp.message == "AI 服务暂时不可用，请稍后重试"
        assert resp.current_round == 1

    @pytest.mark.asyncio
    async def test_llm_service_error_logs_error(
        self, system, cache, prompt_manager, caplog,
    ):
        """Validates: Requirement 7.5 — error is logged."""
        import logging

        mock_client = AsyncMock(spec=LLMClient)
        mock_client.chat_completion = AsyncMock(
            side_effect=LLMServiceError(status_code=503, message="Service down")
        )
        mock_client.build_messages = LLMClient.build_messages

        mgr = SessionManager(
            cache=cache, llm_client=mock_client, prompt_manager=prompt_manager,
        )
        session = await _create_session(system, mgr)

        with caplog.at_level(logging.ERROR, logger="src.interview.system"):
            await mgr.send_message(session.session_id, "t1", "你好")

        assert any("LLM service error" in record.message for record in caplog.records)


class TestSendMessageWithoutLLMClient:
    """Tests for backward compatibility when no LLMClient is injected."""

    @pytest.mark.asyncio
    async def test_stub_response_when_no_llm_client(self, system, cache):
        """Without LLMClient, send_message falls back to stub response."""
        mgr = SessionManager(cache=cache)
        session = await _create_session(system, mgr)
        resp = await mgr.send_message(session.session_id, "t1", "我们需要订单管理")

        assert "感谢您的信息" in resp.message
        assert "订单管理" in resp.message
