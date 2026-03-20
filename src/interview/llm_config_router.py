"""LLM 配置管理 router — 保存、读取、测试连通性。

Admin endpoints:
  POST /api/llm-config/config          — 保存 LLM 配置（admin 权限校验）
  GET  /api/llm-config/config          — 获取当前配置（api_key 掩码返回）
  POST /api/llm-config/config/test     — 测试 LLM 连通性（admin 权限校验）

遵循 baidu_pan_router.py 的 _get_user_info + _require_admin 模式。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from src.interview.config import settings
from src.interview.llm_config_service import LLMConfigService
from src.interview.llm_models import LLMConfigRequest, LLMConfigResponse, ConnectivityResult

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")

llm_config_router = APIRouter(prefix="/api/llm-config", tags=["llm-config"])

_svc = LLMConfigService()


# ---------------------------------------------------------------------------
# Auth helpers (same pattern as baidu_pan_router)
# ---------------------------------------------------------------------------

async def _get_user_info(token: str = Depends(oauth2_scheme)) -> dict:
    """Decode JWT and return user info dict."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {
        "user_id": payload.get("user_id", ""),
        "tenant_id": payload.get("tenant_id", ""),
        "role": payload.get("role", "member"),
    }


def _require_admin(user: dict) -> None:
    """Raise 403 if user is not admin."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作")


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

@llm_config_router.post("/config", response_model=LLMConfigResponse)
async def save_config(body: LLMConfigRequest, user: dict = Depends(_get_user_info)):
    """保存 LLM 配置（UPSERT 语义，admin 权限校验）。"""
    _require_admin(user)
    result = await _svc.save_config(user["tenant_id"], body)
    return result


@llm_config_router.get("/config", response_model=LLMConfigResponse)
async def get_config(user: dict = Depends(_get_user_info)):
    """获取当前租户 LLM 配置（api_key 掩码返回）。"""
    result = await _svc.get_config(user["tenant_id"])
    return result


@llm_config_router.post("/config/test", response_model=ConnectivityResult)
async def test_connectivity(body: LLMConfigRequest, user: dict = Depends(_get_user_info)):
    """测试 LLM 服务连通性（admin 权限校验）。"""
    _require_admin(user)
    result = await _svc.test_connectivity(body)
    return result
