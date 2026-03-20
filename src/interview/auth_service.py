"""Authentication service for user registration, login, and token management.

Provides methods for user registration, login, JWT access token creation,
refresh token management, and token revocation. Integrates with the existing
InterviewSecurity JWT mechanism by using the same JWT_SECRET and JWT_ALGORITHM.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import jwt
from sqlalchemy import text

from src.interview.auth_models import TokenResponse
from src.interview.config import settings
from src.interview.db import async_session_factory


class AuthService:
    """用户认证服务，负责注册、登录、令牌签发与刷新。"""

    async def register(
        self, email: str, password: str, enterprise_code: str
    ) -> TokenResponse:
        """用户注册。

        验证企业号存在性、邮箱唯一性，创建用户并签发令牌对。

        Args:
            email: 企业邮箱（已通过 Pydantic 验证格式和非公共域名）
            password: 用户密码
            enterprise_code: 企业号

        Returns:
            TokenResponse: 包含 access_token 和 refresh_token

        Raises:
            HTTPException: 400 如果企业号不存在或邮箱已被注册
        """
        async with async_session_factory() as session:
            # 1. 查询企业是否存在
            result = await session.execute(
                text(
                    "SELECT id, status FROM enterprises "
                    "WHERE code = :code LIMIT 1"
                ),
                {"code": enterprise_code},
            )
            enterprise = result.fetchone()

            if enterprise is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="企业号不存在",
                )

            enterprise_id, enterprise_status = enterprise

            # 2. 检查企业状态
            if enterprise_status != "active":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="企业已被禁用",
                )

            # 3. 检查邮箱唯一性
            result = await session.execute(
                text(
                    "SELECT 1 FROM users "
                    "WHERE email = :email AND is_deleted = false LIMIT 1"
                ),
                {"email": email.lower()},
            )
            if result.fetchone() is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该邮箱已被注册",
                )

            # 4. 哈希密码
            password_hash = bcrypt.hashpw(
                password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            # 5. 创建用户
            result = await session.execute(
                text(
                    "INSERT INTO users (email, password_hash, enterprise_id, role) "
                    "VALUES (:email, :password_hash, :enterprise_id, :role) "
                    "RETURNING id"
                ),
                {
                    "email": email.lower(),
                    "password_hash": password_hash,
                    "enterprise_id": str(enterprise_id),
                    "role": "member",
                },
            )
            user_id = str(result.fetchone()[0])
            await session.commit()

        # 6. 签发令牌对
        access_token = self.create_access_token(
            user_id=user_id,
            tenant_id=str(enterprise_id),
            role="member",
        )
        refresh_token = await self.create_refresh_token(user_id=user_id)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def login(self, email: str, password: str) -> TokenResponse:
        """用户登录。

        验证邮箱密码、检查企业状态，签发令牌对。

        Args:
            email: 企业邮箱
            password: 用户密码

        Returns:
            TokenResponse: 包含 access_token 和 refresh_token

        Raises:
            HTTPException: 401 如果邮箱或密码错误、企业被禁用或账号被禁用
        """
        async with async_session_factory() as session:
            # 1. 查询用户
            result = await session.execute(
                text(
                    "SELECT u.id, u.password_hash, u.enterprise_id, u.role, "
                    "u.is_active, e.status as enterprise_status "
                    "FROM users u "
                    "JOIN enterprises e ON u.enterprise_id = e.id "
                    "WHERE u.email = :email AND u.is_deleted = false "
                    "LIMIT 1"
                ),
                {"email": email.lower()},
            )
            user = result.fetchone()

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="邮箱或密码错误",
                )

            (
                user_id,
                password_hash,
                enterprise_id,
                role,
                is_active,
                enterprise_status,
            ) = user

            # 2. 验证密码
            if not bcrypt.checkpw(
                password.encode("utf-8"), password_hash.encode("utf-8")
            ):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="邮箱或密码错误",
                )

            # 3. 检查企业状态
            if enterprise_status != "active":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="企业已被禁用",
                )

            # 4. 检查用户状态
            if not is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="账号已被禁用",
                )

        # 5. 签发令牌对
        access_token = self.create_access_token(
            user_id=str(user_id),
            tenant_id=str(enterprise_id),
            role=role,
        )
        refresh_token = await self.create_refresh_token(user_id=str(user_id))

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    def create_access_token(
        self, user_id: str, tenant_id: str, role: str
    ) -> str:
        """创建 JWT access token。

        使用与 InterviewSecurity.get_current_tenant 相同的 JWT_SECRET 和
        JWT_ALGORITHM，确保兼容性。

        Args:
            user_id: 用户 ID
            tenant_id: 租户 ID（= enterprise_id）
            role: 用户角色（admin 或 member）

        Returns:
            str: JWT access token
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {
            "user_id": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "exp": expire,
            "iat": now,
        }

        return jwt.encode(
            payload,
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )

    async def create_refresh_token(self, user_id: str) -> str:
        """创建 refresh token。

        生成随机 token，将其哈希值存储到数据库，返回原始 token。

        Args:
            user_id: 用户 ID

        Returns:
            str: 原始 refresh token（用于返回给客户端）
        """
        # 1. 生成随机 token
        raw_token = secrets.token_urlsafe(32)

        # 2. 计算哈希值
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # 3. 计算过期时间
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        # 4. 存储到数据库
        async with async_session_factory() as session:
            await session.execute(
                text(
                    "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) "
                    "VALUES (:user_id, :token_hash, :expires_at)"
                ),
                {
                    "user_id": user_id,
                    "token_hash": token_hash,
                    "expires_at": expires_at,
                },
            )
            await session.commit()

        return raw_token

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """刷新令牌。

        验证 refresh token，标记旧 token 已使用，签发新令牌对。

        Args:
            refresh_token: 客户端提供的 refresh token

        Returns:
            TokenResponse: 包含新的 access_token 和 refresh_token

        Raises:
            HTTPException: 401 如果 token 无效、已使用或已过期
        """
        # 1. 计算 token 哈希
        token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()

        async with async_session_factory() as session:
            # 2. 查询 token 记录
            result = await session.execute(
                text(
                    "SELECT id, user_id, is_used, expires_at "
                    "FROM refresh_tokens "
                    "WHERE token_hash = :token_hash "
                    "LIMIT 1"
                ),
                {"token_hash": token_hash},
            )
            token_record = result.fetchone()

            if token_record is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效的刷新令牌",
                )

            token_id, user_id, is_used, expires_at = token_record

            # 3. 检查是否已使用
            if is_used:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="刷新令牌已被使用",
                )

            # 4. 检查是否过期
            now = datetime.now(timezone.utc)
            # Handle timezone-naive expires_at from database
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="刷新令牌已过期",
                )

            # 5. 标记旧 token 已使用
            await session.execute(
                text(
                    "UPDATE refresh_tokens SET is_used = true "
                    "WHERE id = :token_id"
                ),
                {"token_id": str(token_id)},
            )

            # 6. 查询用户和企业信息
            result = await session.execute(
                text(
                    "SELECT u.id, u.enterprise_id, u.role "
                    "FROM users u "
                    "WHERE u.id = :user_id AND u.is_deleted = false "
                    "LIMIT 1"
                ),
                {"user_id": str(user_id)},
            )
            user = result.fetchone()

            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="用户不存在",
                )

            user_id_str, enterprise_id, role = user
            await session.commit()

        # 7. 签发新令牌对
        access_token = self.create_access_token(
            user_id=str(user_id_str),
            tenant_id=str(enterprise_id),
            role=role,
        )
        new_refresh_token = await self.create_refresh_token(
            user_id=str(user_id_str)
        )

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def revoke_refresh_token(self, token: str) -> None:
        """撤销 refresh token。

        将 token 标记为已使用。

        Args:
            token: 要撤销的 refresh token
        """
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        async with async_session_factory() as session:
            await session.execute(
                text(
                    "UPDATE refresh_tokens SET is_used = true "
                    "WHERE token_hash = :token_hash"
                ),
                {"token_hash": token_hash},
            )
            await session.commit()
