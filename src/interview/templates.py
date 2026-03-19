"""Industry template management — seed data and CRUD operations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from src.interview.models import IndustryTemplateRequest, IndustryTemplateResponse

# ---------------------------------------------------------------------------
# In-memory store (replaced by PostgreSQL in production)
# ---------------------------------------------------------------------------

_templates: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Seed data — 3 built-in industry templates
# ---------------------------------------------------------------------------

SEED_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "金融行业模板",
        "industry": "finance",
        "system_prompt": (
            "你是业务规则 elicitation 专家。当前项目领域：金融。"
            "目标：引导用户说出所有业务规则、实体、属性，尤其隐性内容"
            "（假设、例外、边界条件）。每次回复最多问 1-2 个问题，"
            '使用"追问""举例""反向确认"技巧。'
        ),
        "config": {"max_rounds": 30, "focus_areas": ["风控规则", "账户体系", "交易流程"]},
        "is_builtin": True,
    },
    {
        "name": "电商行业模板",
        "industry": "ecommerce",
        "system_prompt": (
            "你是业务规则 elicitation 专家。当前项目领域：电商。"
            "目标：引导用户说出所有业务规则、实体、属性，尤其隐性内容"
            "（假设、例外、边界条件）。每次回复最多问 1-2 个问题，"
            '使用"追问""举例""反向确认"技巧。'
        ),
        "config": {"max_rounds": 30, "focus_areas": ["商品管理", "订单流程", "促销规则"]},
        "is_builtin": True,
    },
    {
        "name": "制造行业模板",
        "industry": "manufacturing",
        "system_prompt": (
            "你是业务规则 elicitation 专家。当前项目领域：制造。"
            "目标：引导用户说出所有业务规则、实体、属性，尤其隐性内容"
            "（假设、例外、边界条件）。每次回复最多问 1-2 个问题，"
            '使用"追问""举例""反向确认"技巧。'
        ),
        "config": {"max_rounds": 30, "focus_areas": ["生产工艺", "质量检测", "供应链"]},
        "is_builtin": True,
    },
]


def _seed() -> None:
    """Populate the in-memory store with built-in templates (idempotent)."""
    if _templates:
        return
    for seed in SEED_TEMPLATES:
        tid = uuid.uuid4().hex
        _templates[tid] = {**seed, "id": tid, "created_at": _now(), "updated_at": _now()}


def _to_response(data: dict[str, Any]) -> IndustryTemplateResponse:
    return IndustryTemplateResponse(
        id=data["id"],
        name=data["name"],
        industry=data["industry"],
        system_prompt=data["system_prompt"],
        config=data.get("config", {}),
        is_builtin=data.get("is_builtin", False),
        created_at=data["created_at"],
    )


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


def list_templates(industry: str | None = None) -> list[IndustryTemplateResponse]:
    """Return all templates, optionally filtered by industry."""
    _seed()
    results = _templates.values()
    if industry:
        results = [t for t in results if t["industry"] == industry]
    return [_to_response(t) for t in results]


def get_template(template_id: str) -> IndustryTemplateResponse | None:
    """Return a single template by ID, or None."""
    _seed()
    data = _templates.get(template_id)
    return _to_response(data) if data else None


def get_template_by_industry(industry: str) -> IndustryTemplateResponse | None:
    """Return the first template matching the given industry."""
    _seed()
    for t in _templates.values():
        if t["industry"] == industry:
            return _to_response(t)
    return None


def create_template(req: IndustryTemplateRequest) -> IndustryTemplateResponse:
    """Create a new template and return it."""
    _seed()
    tid = uuid.uuid4().hex
    now = _now()
    data = {
        "id": tid,
        "name": req.name,
        "industry": req.industry,
        "system_prompt": req.system_prompt,
        "config": req.config,
        "is_builtin": False,
        "created_at": now,
        "updated_at": now,
    }
    _templates[tid] = data
    return _to_response(data)


def update_template(template_id: str, req: IndustryTemplateRequest) -> IndustryTemplateResponse | None:
    """Update an existing template. Returns None if not found."""
    _seed()
    data = _templates.get(template_id)
    if data is None:
        return None
    data.update(
        name=req.name,
        industry=req.industry,
        system_prompt=req.system_prompt,
        config=req.config,
        updated_at=_now(),
    )
    return _to_response(data)


def reset_templates() -> None:
    """Clear all templates (for testing)."""
    _templates.clear()
