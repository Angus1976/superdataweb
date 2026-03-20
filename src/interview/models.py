"""Pydantic data models for the interview module.

Defines Entity, Rule, Relation, AIFriendlyLabel, ProjectCreateRequest,
ExtractionResult, and related models used across all sub-modules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core label models
# ---------------------------------------------------------------------------


class EntityAttribute(BaseModel):
    """实体属性定义。"""

    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    required: bool = False
    values: list[str] = []


class Entity(BaseModel):
    """业务实体。"""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    attributes: list[EntityAttribute] = []
    source: Optional[str] = None


class Rule(BaseModel):
    """业务规则。"""

    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    condition: str = Field(..., min_length=1)
    action: str = Field(..., min_length=1)
    priority: str = "medium"
    related_entities: list[str] = []


class Relation(BaseModel):
    """实体间关系。"""

    id: str = Field(..., min_length=1)
    source_entity: str = Field(..., min_length=1)
    target_entity: str = Field(..., min_length=1)
    relation_type: str = Field(..., min_length=1)
    attributes: dict[str, Any] = {}


class AIFriendlyLabel(BaseModel):
    """AI 友好型数据标签，包含实体、规则和关系。"""

    entities: list[Entity] = []
    rules: list[Rule] = []
    relations: list[Relation] = []


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ProjectCreateRequest(BaseModel):
    """项目创建请求。"""

    name: str = Field(..., min_length=1, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    business_domain: Optional[str] = None


class ProjectResponse(BaseModel):
    """项目响应。"""

    id: str
    tenant_id: str
    name: str
    industry: Optional[str] = None
    business_domain: Optional[str] = None
    status: str = "active"
    created_at: datetime


class ExtractionResult(BaseModel):
    """实体提取结果。"""

    entities: list[Entity] = []
    rules: list[Rule] = []
    relations: list[Relation] = []
    confidence: float = 0.0


class IndustryTemplateRequest(BaseModel):
    """行业模板创建/更新请求。"""

    name: str = Field(..., min_length=1, max_length=100)
    industry: str = Field(..., min_length=1)
    system_prompt: str = Field(..., min_length=1)
    config: dict[str, Any] = {}


class IndustryTemplateResponse(BaseModel):
    """行业模板响应。"""

    id: str
    name: str
    industry: str
    system_prompt: str
    config: dict[str, Any] = {}
    is_builtin: bool = False
    created_at: datetime


class ValidationResult(BaseModel):
    """通用校验结果。"""

    is_valid: bool
    errors: list[str] = []
