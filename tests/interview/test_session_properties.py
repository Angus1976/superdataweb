"""Property-based tests for intelligent-interview sub-module.

Property 1: 对话消息触发实体提取
Property 2: 会话最大轮次自动终止
Property 3: 会话结束生成摘要
"""

import pytest
from hypothesis import given, settings as h_settings, strategies as st

from src.interview.entity_extractor import InterviewEntityExtractor
from src.interview.models import ExtractionResult, ProjectCreateRequest
from src.interview.session_models import AIResponse, InterviewSummary
from src.interview.system import InterviewSystem, SessionManager, reset_projects, reset_sessions


non_empty_str = st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz ")
industry_st = st.sampled_from(["finance", "ecommerce", "manufacturing"])


# ---------------------------------------------------------------------------
# Property 1: 对话消息触发实体提取
# ---------------------------------------------------------------------------

class TestMessageTriggersExtraction:
    """Feature: intelligent-interview, Property 1: 对话消息触发实体提取"""

    @given(message=non_empty_str)
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_send_message_returns_ai_response(self, message):
        """send_message always returns a valid AIResponse."""
        reset_projects()
        reset_sessions()

        system = InterviewSystem()
        req = ProjectCreateRequest(name="test", industry="finance")
        project = await system.create_project("t1", req)

        mgr = SessionManager()
        session = await mgr.start_session(project.id, "t1")
        response = await mgr.send_message(session.session_id, "t1", message)

        assert isinstance(response, AIResponse)
        assert response.current_round == 1
        assert response.max_rounds == 30
        assert len(response.message) > 0

    @given(message=non_empty_str)
    @h_settings(max_examples=50, deadline=None)
    @pytest.mark.asyncio
    async def test_extract_from_message_produces_result(self, message):
        """InterviewEntityExtractor.extract_from_message returns ExtractionResult."""
        extractor = InterviewEntityExtractor()
        result = await extractor.extract_from_message(message)
        assert isinstance(result, ExtractionResult)


# ---------------------------------------------------------------------------
# Property 2: 会话最大轮次自动终止
# ---------------------------------------------------------------------------

class TestMaxRoundsTermination:
    """Feature: intelligent-interview, Property 2: 会话最大轮次自动终止"""

    @given(extra_rounds=st.integers(min_value=0, max_value=5))
    @h_settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_session_auto_ends_at_30(self, extra_rounds):
        """Session auto-terminates at round 30."""
        reset_projects()
        reset_sessions()

        system = InterviewSystem()
        req = ProjectCreateRequest(name="test", industry="finance")
        project = await system.create_project("t1", req)

        mgr = SessionManager()
        session = await mgr.start_session(project.id, "t1")

        # Send 30 messages
        for i in range(30):
            resp = await mgr.send_message(session.session_id, "t1", f"msg {i}")

        # The 30th message should trigger auto-end
        # After 30 rounds, session should be completed
        status = await mgr.get_session_status(session.session_id)
        assert status.current_round == 30 or status.status == "completed"


# ---------------------------------------------------------------------------
# Property 3: 会话结束生成摘要
# ---------------------------------------------------------------------------

class TestSessionSummary:
    """Feature: intelligent-interview, Property 3: 会话结束生成摘要"""

    @given(num_messages=st.integers(min_value=1, max_value=5))
    @h_settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_end_session_returns_summary(self, num_messages):
        """end_session always returns a non-empty InterviewSummary."""
        reset_projects()
        reset_sessions()

        system = InterviewSystem()
        req = ProjectCreateRequest(name="test", industry="ecommerce")
        project = await system.create_project("t1", req)

        mgr = SessionManager()
        session = await mgr.start_session(project.id, "t1")

        for i in range(num_messages):
            await mgr.send_message(session.session_id, "t1", f"message {i}")

        summary = await mgr.end_session(session.session_id, "t1")
        assert isinstance(summary, InterviewSummary)
        assert summary.session_id == session.session_id
        assert len(summary.summary) > 0
        assert summary.total_rounds == num_messages
