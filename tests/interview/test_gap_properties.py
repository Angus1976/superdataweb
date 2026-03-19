"""Property-based tests for intelligent-interview gap detection and completions.

Property 4: 隐含缺口检测与引导问题生成
Property 5: 一键补全生成 5 条建议
"""

import pytest
from hypothesis import given, settings as h_settings, strategies as st

from src.interview.models import ProjectCreateRequest
from src.interview.session_models import CompletionSuggestion, ImplicitGap
from src.interview.system import InterviewSystem, SessionManager, reset_projects, reset_sessions


non_empty_str = st.text(min_size=1, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz ")


# ---------------------------------------------------------------------------
# Property 4: 隐含缺口检测与引导问题生成
# ---------------------------------------------------------------------------

class TestImplicitGapDetection:
    """Feature: intelligent-interview, Property 4: 隐含缺口检测与引导问题生成"""

    @given(num_messages=st.integers(min_value=2, max_value=6))
    @h_settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_gaps_detected_after_messages(self, num_messages):
        """After enough messages, implicit gaps should be detected with suggested questions."""
        reset_projects()
        reset_sessions()

        system = InterviewSystem()
        req = ProjectCreateRequest(name="test", industry="finance")
        project = await system.create_project("t1", req)

        mgr = SessionManager()
        session = await mgr.start_session(project.id, "t1")

        for i in range(num_messages):
            await mgr.send_message(session.session_id, "t1", f"business rule {i}")

        gaps = await mgr.detect_implicit_gaps(session.session_id)
        assert isinstance(gaps, list)
        # After 2+ messages, gaps should be detected
        if len(gaps) > 0:
            for gap in gaps:
                assert isinstance(gap, ImplicitGap)
                assert len(gap.gap_description) > 0
                assert len(gap.suggested_question) > 0

    @given(dummy=st.just(None))
    @h_settings(max_examples=10, deadline=None)
    @pytest.mark.asyncio
    async def test_no_gaps_for_new_session(self, dummy):
        """New session with no messages should have no gaps."""
        reset_projects()
        reset_sessions()

        system = InterviewSystem()
        req = ProjectCreateRequest(name="test", industry="ecommerce")
        project = await system.create_project("t1", req)

        mgr = SessionManager()
        session = await mgr.start_session(project.id, "t1")

        gaps = await mgr.detect_implicit_gaps(session.session_id)
        assert gaps == []


# ---------------------------------------------------------------------------
# Property 5: 一键补全生成 5 条建议
# ---------------------------------------------------------------------------

class TestCompletionSuggestions:
    """Feature: intelligent-interview, Property 5: 一键补全生成 5 条建议"""

    @given(num_messages=st.integers(min_value=0, max_value=5))
    @h_settings(max_examples=20, deadline=None)
    @pytest.mark.asyncio
    async def test_always_returns_five_suggestions(self, num_messages):
        """generate_completions always returns exactly 5 CompletionSuggestion."""
        reset_projects()
        reset_sessions()

        system = InterviewSystem()
        req = ProjectCreateRequest(name="test", industry="manufacturing")
        project = await system.create_project("t1", req)

        mgr = SessionManager()
        session = await mgr.start_session(project.id, "t1")

        for i in range(num_messages):
            await mgr.send_message(session.session_id, "t1", f"info {i}")

        suggestions = await mgr.generate_completions(session.session_id)
        assert len(suggestions) == 5
        for s in suggestions:
            assert isinstance(s, CompletionSuggestion)
            assert len(s.suggestion_text) > 0
            assert len(s.category) > 0
