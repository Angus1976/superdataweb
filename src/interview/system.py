"""InterviewSystem — core project and session management.

This module provides project creation with tenant isolation.
Session management methods will be added by the intelligent-interview sub-module.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from src.interview.models import ProjectCreateRequest, ProjectResponse


# ---------------------------------------------------------------------------
# In-memory project store (replaced by PostgreSQL in production)
# ---------------------------------------------------------------------------

_projects: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class InterviewSystem:
    """访谈系统核心 — 项目管理与会话控制。"""

    async def create_project(
        self, tenant_id: str, data: ProjectCreateRequest
    ) -> ProjectResponse:
        """创建项目，存储至 PostgreSQL JSONB。"""
        pid = uuid.uuid4().hex
        now = _now()
        record = {
            "id": pid,
            "tenant_id": tenant_id,
            "name": data.name,
            "industry": data.industry,
            "business_domain": data.business_domain,
            "raw_requirements": {},
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        _projects[pid] = record
        return ProjectResponse(
            id=pid,
            tenant_id=tenant_id,
            name=data.name,
            industry=data.industry,
            business_domain=data.business_domain,
            status="active",
            created_at=now,
        )

    async def list_projects(self, tenant_id: str) -> list[ProjectResponse]:
        """列出当前租户的所有项目（租户隔离）。"""
        results = []
        for p in _projects.values():
            if p["tenant_id"] == tenant_id:
                results.append(
                    ProjectResponse(
                        id=p["id"],
                        tenant_id=p["tenant_id"],
                        name=p["name"],
                        industry=p["industry"],
                        business_domain=p.get("business_domain"),
                        status=p["status"],
                        created_at=p["created_at"],
                    )
                )
        return results

    async def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Get a project by ID."""
        return _projects.get(project_id)


def reset_projects() -> None:
    """Clear all projects (for testing)."""
    _projects.clear()


# ---------------------------------------------------------------------------
# Session management (intelligent-interview sub-module)
# ---------------------------------------------------------------------------

import json
from src.interview.session_models import (
    AIResponse,
    CompletionSuggestion,
    ImplicitGap,
    InterviewSummary,
    SessionResponse,
    SessionStatus,
)
from src.interview.session_cache import SessionCache
from src.interview import templates as tmpl_store

# In-memory session store (replaced by PostgreSQL in production)
_sessions: dict[str, dict[str, Any]] = {}
_messages: dict[str, list[dict[str, Any]]] = {}

# Default session cache (in-memory for testing)
_default_cache = SessionCache()


class SessionManager:
    """会话管理器 — 管理访谈会话生命周期。"""

    def __init__(self, cache: SessionCache | None = None, security: Any = None) -> None:
        self._cache = cache or _default_cache
        self._security = security

    async def start_session(
        self, project_id: str, tenant_id: str
    ) -> SessionResponse:
        """启动访谈会话。"""
        # Load industry template for the project
        project = _projects.get(project_id)
        template_name = None
        if project:
            tmpl = tmpl_store.get_template_by_industry(project.get("industry", ""))
            if tmpl:
                template_name = tmpl.name

        sid = uuid.uuid4().hex
        now = _now()
        session = {
            "id": sid,
            "project_id": project_id,
            "tenant_id": tenant_id,
            "current_round": 0,
            "max_rounds": 30,
            "status": "active",
            "template_name": template_name,
            "created_at": now,
        }
        _sessions[sid] = session
        _messages[sid] = []

        # Initialize Redis cache
        await self._cache.save_context(sid, {
            "messages": [],
            "current_round": 0,
            "project_id": project_id,
            "tenant_id": tenant_id,
            "template_name": template_name,
        })

        return SessionResponse(
            session_id=sid,
            project_id=project_id,
            status="active",
            current_round=0,
            max_rounds=30,
            template_name=template_name,
            created_at=now,
        )

    async def send_message(
        self, session_id: str, tenant_id: str, message: str
    ) -> AIResponse:
        """处理客户消息。"""
        session = _sessions.get(session_id)
        if not session:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=404, detail="Session not found")

        if session["status"] != "active":
            from fastapi import HTTPException, status
            raise HTTPException(status_code=409, detail="Session already ended")

        # Acquire lock
        locked = await self._cache.acquire_lock(session_id)
        if not locked:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=409, detail="Session is processing, please retry")

        try:
            current_round = session["current_round"]

            # Check max rounds
            if current_round >= 30:
                summary = await self.end_session(session_id, tenant_id)
                return AIResponse(
                    message=f"访谈已达到最大轮次（30轮），自动结束。{summary.summary}",
                    implicit_gaps=[],
                    current_round=30,
                    max_rounds=30,
                )

            # Sanitize content
            sanitized = message
            if self._security:
                sanitized = self._security.sanitize_content(message)

            # Generate AI response (stub — real LLM integration in production)
            ai_message = f"感谢您的信息。关于「{sanitized[:50]}」，请问还有哪些具体的业务规则需要补充？"

            # Detect implicit gaps
            gaps = await self.detect_implicit_gaps(session_id)

            # Update session state
            session["current_round"] = current_round + 1

            # Store message
            msg_record = {
                "role": "user",
                "content": message,
                "sanitized_content": sanitized,
                "round_number": current_round + 1,
            }
            _messages.setdefault(session_id, []).append(msg_record)
            _messages[session_id].append({
                "role": "assistant",
                "content": ai_message,
                "sanitized_content": ai_message,
                "round_number": current_round + 1,
            })

            # Update cache
            await self._cache.save_context(session_id, {
                "messages": _messages[session_id],
                "current_round": current_round + 1,
                "project_id": session["project_id"],
                "tenant_id": tenant_id,
            })

            return AIResponse(
                message=ai_message,
                implicit_gaps=gaps,
                current_round=current_round + 1,
                max_rounds=30,
            )
        finally:
            await self._cache.release_lock(session_id)

    async def detect_implicit_gaps(self, session_id: str) -> list[ImplicitGap]:
        """分析对话上下文，检测隐含信息缺口。"""
        msgs = _messages.get(session_id, [])
        if len(msgs) < 2:
            return []

        # Stub: generate sample gaps based on conversation length
        return [
            ImplicitGap(
                gap_description="业务规则的边界条件未明确",
                suggested_question="请描述该规则在极端情况下的处理方式",
            )
        ]

    async def generate_completions(self, session_id: str) -> list[CompletionSuggestion]:
        """基于上下文生成 5 条补全建议。"""
        return [
            CompletionSuggestion(suggestion_text="建议补充实体的属性约束", category="entity_attribute"),
            CompletionSuggestion(suggestion_text="建议描述异常处理规则", category="business_rule"),
            CompletionSuggestion(suggestion_text="建议明确实体间的关联关系", category="relation"),
            CompletionSuggestion(suggestion_text="建议补充审批流程细节", category="workflow"),
            CompletionSuggestion(suggestion_text="建议说明数据校验规则", category="business_rule"),
        ]

    async def end_session(self, session_id: str, tenant_id: str) -> InterviewSummary:
        """结束会话。"""
        session = _sessions.get(session_id)
        if not session:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=404, detail="Session not found")

        now = _now()
        session["status"] = "completed"
        session["ended_at"] = now

        msgs = _messages.get(session_id, [])
        total_rounds = session["current_round"]

        summary = InterviewSummary(
            session_id=session_id,
            summary=f"本次访谈共进行 {total_rounds} 轮对话，收集了业务实体和规则信息。",
            entities=[],
            rules=[],
            relations=[],
            total_rounds=total_rounds,
            ended_at=now,
        )

        # Clean up cache
        await self._cache.delete_context(session_id)

        return summary

    async def get_session_status(self, session_id: str) -> SessionStatus:
        """获取会话状态。"""
        session = _sessions.get(session_id)
        if not session:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionStatus(
            session_id=session_id,
            status=session["status"],
            current_round=session["current_round"],
            max_rounds=session["max_rounds"],
            pending_tasks=[],
        )


def reset_sessions() -> None:
    """Clear all sessions (for testing)."""
    _sessions.clear()
    _messages.clear()
