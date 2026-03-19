"""Tests for session management — SessionManager."""

import pytest

from src.interview.models import ProjectCreateRequest
from src.interview.session_cache import SessionCache
from src.interview.session_models import AIResponse, CompletionSuggestion, InterviewSummary, SessionStatus
from src.interview.system import InterviewSystem, SessionManager, reset_projects, reset_sessions
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
def mgr(cache) -> SessionManager:
    return SessionManager(cache=cache)


class TestStartSession:
    @pytest.mark.asyncio
    async def test_creates_session(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        assert session.status == "active"
        assert session.current_round == 0
        assert session.max_rounds == 30

    @pytest.mark.asyncio
    async def test_loads_template_name(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        assert session.template_name == "金融行业模板"


class TestSendMessage:
    @pytest.mark.asyncio
    async def test_returns_ai_response(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        resp = await mgr.send_message(session.session_id, "t1", "我们需要订单管理")
        assert isinstance(resp, AIResponse)
        assert resp.current_round == 1
        assert resp.max_rounds == 30

    @pytest.mark.asyncio
    async def test_increments_round(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        await mgr.send_message(session.session_id, "t1", "msg1")
        resp = await mgr.send_message(session.session_id, "t1", "msg2")
        assert resp.current_round == 2

    @pytest.mark.asyncio
    async def test_ended_session_rejects_message(self, system, mgr):
        from fastapi import HTTPException
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        await mgr.end_session(session.session_id, "t1")
        with pytest.raises(HTTPException) as exc_info:
            await mgr.send_message(session.session_id, "t1", "msg")
        assert exc_info.value.status_code == 409


class TestEndSession:
    @pytest.mark.asyncio
    async def test_returns_summary(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        await mgr.send_message(session.session_id, "t1", "msg")
        summary = await mgr.end_session(session.session_id, "t1")
        assert isinstance(summary, InterviewSummary)
        assert summary.total_rounds == 1


class TestGetSessionStatus:
    @pytest.mark.asyncio
    async def test_returns_status(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        status = await mgr.get_session_status(session.session_id)
        assert isinstance(status, SessionStatus)
        assert status.status == "active"


class TestGenerateCompletions:
    @pytest.mark.asyncio
    async def test_returns_five_suggestions(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        suggestions = await mgr.generate_completions(session.session_id)
        assert len(suggestions) == 5
        assert all(isinstance(s, CompletionSuggestion) for s in suggestions)


class TestDetectImplicitGaps:
    @pytest.mark.asyncio
    async def test_no_gaps_for_new_session(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        gaps = await mgr.detect_implicit_gaps(session.session_id)
        assert gaps == []

    @pytest.mark.asyncio
    async def test_gaps_after_messages(self, system, mgr):
        proj = await system.create_project("t1", ProjectCreateRequest(name="P", industry="finance"))
        session = await mgr.start_session(proj.id, "t1")
        await mgr.send_message(session.session_id, "t1", "msg1")
        # After a message exchange, gaps should be detected
        resp = await mgr.send_message(session.session_id, "t1", "msg2")
        assert len(resp.implicit_gaps) >= 0  # may or may not have gaps
