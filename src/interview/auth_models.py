"""Pydantic models for user authentication and enterprise management.

Defines request/response models for auth endpoints (register, login, refresh),
user management endpoints (CRUD, batch import), and related types.
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# Public email domains that are rejected during enterprise registration
PUBLIC_EMAIL_DOMAINS: set[str] = {
    "gmail.com",
    "qq.com",
    "163.com",
    "126.com",
    "hotmail.com",
    "outlook.com",
    "yahoo.com",
}


# ---------------------------------------------------------------------------
# Auth request / response models
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """用户注册请求。"""

    email: str = Field(..., description="企业邮箱")
    password: str = Field(..., min_length=8, description="密码")
    enterprise_code: str = Field(..., min_length=1, description="企业号")

    @field_validator("email")
    @classmethod
    def validate_enterprise_email(cls, v: str) -> str:
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(pattern, v):
            raise ValueError("邮箱格式无效")
        domain = v.split("@")[1].lower()
        if domain in PUBLIC_EMAIL_DOMAINS:
            raise ValueError("请使用企业邮箱注册")
        return v.lower()


class LoginRequest(BaseModel):
    """用户登录请求。"""

    email: str = Field(..., description="企业邮箱")
    password: str = Field(..., min_length=1, description="密码")


class RefreshRequest(BaseModel):
    """令牌刷新请求。"""

    refresh_token: str


class TokenResponse(BaseModel):
    """令牌响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


# ---------------------------------------------------------------------------
# User management models
# ---------------------------------------------------------------------------


class UserCreateRequest(BaseModel):
    """管理员创建用户请求。"""

    email: str
    password: str = Field(..., min_length=8)
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class UserUpdateRequest(BaseModel):
    """管理员更新用户请求。"""

    role: str | None = Field(default=None, pattern=r"^(admin|member)$")
    is_active: bool | None = None


class UserResponse(BaseModel):
    """用户响应。"""

    id: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


class PaginatedUsers(BaseModel):
    """分页用户列表。"""

    items: list[UserResponse]
    total: int
    page: int
    size: int


# ---------------------------------------------------------------------------
# Batch import models
# ---------------------------------------------------------------------------


class BatchImportError(BaseModel):
    """批量导入单行错误。"""

    row: int
    reason: str


class BatchImportResult(BaseModel):
    """批量导入结果摘要。"""

    success_count: int
    failure_count: int
    errors: list[BatchImportError]


# ---------------------------------------------------------------------------
# Enterprise management models
# ---------------------------------------------------------------------------


class EnterpriseCreateRequest(BaseModel):
    """管理员创建企业请求。"""

    name: str = Field(..., min_length=1, description="企业名称")
    code: str = Field(..., min_length=1, description="企业号")
    domain: str | None = Field(default=None, description="企业域名")


class EnterpriseResponse(BaseModel):
    """企业响应。"""

    id: str
    name: str
    code: str
    domain: str | None
    status: str
    created_at: datetime


class EnterpriseListResponse(BaseModel):
    """企业列表响应。"""

    items: list[EnterpriseResponse]
