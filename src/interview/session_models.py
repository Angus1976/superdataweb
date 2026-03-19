"""Pydantic models for the intelligent-interview sub-module.

Defines session, message, gap detection, completion suggestion,
and summary models used by the interview system.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class InterviewMessage(BaseModel):
    """客户发送的对话消息。"""
    content: str = Field(..., min_length=1)


class ImplicitGap(BaseModel):
    """隐含信息缺口。"""
    gap_description: str
    suggested_question: str


class AIResponse(BaseModel):
    """AI 对话响应。"""
    message: str
    implicit_gaps: list[ImplicitGap] = []
    current_round: int
    max_rounds: int


class CompletionSuggestion(BaseModel):
    """补全建议。"""
    suggestion_text: str
    category: str  # business_rule, entity_attribute, relation, workflow


class InterviewSummary(BaseModel):
    """访谈摘要。"""
    session_id: str
    summary: str
    entities: list[dict] = []
    rules: list[dict] = []
    relations: list[dict] = []
    total_rounds: int
    ended_at: datetime


class PendingTask(BaseModel):
    """异步任务状态。"""
    task_id: str
    type: str  # entity_extraction
    status: str  # processing, completed, failed


class SessionStatus(BaseModel):
    """会话状态。"""
    session_id: str
    status: str  # active, completed, terminated
    current_round: int
    max_rounds: int
    pending_tasks: list[PendingTask] = []


class SessionResponse(BaseModel):
    """会话创建响应。"""
    session_id: str
    project_id: str
    status: str = "active"
    current_round: int = 0
    max_rounds: int = 30
    template_name: Optional[str] = None
    created_at: datetime
