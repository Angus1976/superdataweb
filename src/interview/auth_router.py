"""Authentication router for register, login, and token refresh endpoints.

All endpoints are public (no authentication required).
"""

from __future__ import annotations

from fastapi import APIRouter

from src.interview.auth_models import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from src.interview.auth_service import AuthService

auth_router = APIRouter(prefix="/api/auth", tags=["auth"])

_auth_service = AuthService()


@auth_router.post("/register", response_model=TokenResponse)
async def register(data: RegisterRequest) -> TokenResponse:
    """用户注册（无需认证）。"""
    return await _auth_service.register(data.email, data.password, data.enterprise_code)


@auth_router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest) -> TokenResponse:
    """用户登录（无需认证）。"""
    return await _auth_service.login(data.email, data.password)


@auth_router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest) -> TokenResponse:
    """刷新令牌（无需认证，需提供 Refresh Token）。"""
    return await _auth_service.refresh_token(data.refresh_token)
