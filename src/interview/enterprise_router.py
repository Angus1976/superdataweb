"""Enterprise management router.

Provides endpoints for listing enterprises (public) and creating enterprises (admin only).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text

from src.interview.auth_models import (
    EnterpriseCreateRequest,
    EnterpriseListResponse,
    EnterpriseResponse,
)
from src.interview.db import async_session_factory
from src.interview.user_router import require_admin

enterprise_router = APIRouter(prefix="/api/enterprises", tags=["enterprises"])


@enterprise_router.get("", response_model=EnterpriseListResponse)
async def list_enterprises() -> EnterpriseListResponse:
    """查询所有活跃企业（公开接口，注册时使用）。"""
    async with async_session_factory() as session:
        result = await session.execute(
            text(
                "SELECT id, name, code, domain, status, created_at "
                "FROM enterprises WHERE status = 'active' "
                "ORDER BY created_at DESC"
            )
        )
        rows = result.fetchall()

    items = [
        EnterpriseResponse(
            id=str(r[0]), name=r[1], code=r[2],
            domain=r[3], status=r[4], created_at=r[5],
        )
        for r in rows
    ]
    return EnterpriseListResponse(items=items)


@enterprise_router.post("", response_model=EnterpriseResponse)
async def create_enterprise(
    data: EnterpriseCreateRequest,
    current_user: dict = Depends(require_admin),
) -> EnterpriseResponse:
    """创建企业（Admin 权限）。"""
    async with async_session_factory() as session:
        # Check code uniqueness
        result = await session.execute(
            text("SELECT 1 FROM enterprises WHERE code = :code LIMIT 1"),
            {"code": data.code},
        )
        if result.fetchone() is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="企业号已存在",
            )

        result = await session.execute(
            text(
                "INSERT INTO enterprises (name, code, domain) "
                "VALUES (:name, :code, :domain) "
                "RETURNING id, name, code, domain, status, created_at"
            ),
            {"name": data.name, "code": data.code, "domain": data.domain},
        )
        row = result.fetchone()
        await session.commit()

    return EnterpriseResponse(
        id=str(row[0]), name=row[1], code=row[2],
        domain=row[3], status=row[4], created_at=row[5],
    )
