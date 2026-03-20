"""User management service.

Provides methods for listing, creating, updating, deleting users,
and batch importing users from Excel/CSV files.
"""

from __future__ import annotations

import csv
import io
import re

import bcrypt
from fastapi import HTTPException, status
from sqlalchemy import text

from src.interview.auth_models import (
    BatchImportError,
    BatchImportResult,
    PaginatedUsers,
    UserResponse,
    UserCreateRequest,
    UserUpdateRequest,
)
from src.interview.db import async_session_factory

# Maximum rows allowed in a single batch import
_MAX_IMPORT_ROWS = 500

# Minimal email regex for batch import validation
_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
)


def _row_to_user_response(row) -> UserResponse:
    """Convert a database row tuple to a UserResponse."""
    return UserResponse(
        id=str(row[0]),
        email=row[1],
        role=row[2],
        is_active=row[3],
        created_at=row[4],
    )


class UserService:
    """用户管理服务，负责企业用户的增删改查和批量导入。"""

    async def list_users(
        self,
        tenant_id: str,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
    ) -> PaginatedUsers:
        """分页查询本企业用户。

        Args:
            tenant_id: 企业 ID
            page: 页码（从 1 开始）
            size: 每页数量
            search: 可选的邮箱搜索关键词

        Returns:
            PaginatedUsers: 分页用户列表
        """
        offset = (page - 1) * size

        async with async_session_factory() as session:
            # Build base conditions
            base_where = "enterprise_id = :tenant_id AND is_deleted = false"
            params: dict = {"tenant_id": tenant_id}

            if search:
                base_where += " AND email ILIKE :search"
                params["search"] = f"%{search}%"

            # Count total
            count_sql = f"SELECT COUNT(*) FROM users WHERE {base_where}"
            result = await session.execute(text(count_sql), params)
            total = result.scalar() or 0

            # Fetch page
            query_sql = (
                f"SELECT id, email, role, is_active, created_at "
                f"FROM users WHERE {base_where} "
                f"ORDER BY created_at DESC "
                f"LIMIT :limit OFFSET :offset"
            )
            params["limit"] = size
            params["offset"] = offset

            result = await session.execute(text(query_sql), params)
            rows = result.fetchall()

        items = [_row_to_user_response(row) for row in rows]

        return PaginatedUsers(
            items=items,
            total=total,
            page=page,
            size=size,
        )

    async def create_user(
        self, tenant_id: str, data: UserCreateRequest
    ) -> UserResponse:
        """管理员创建用户。

        Args:
            tenant_id: 企业 ID
            data: 用户创建请求

        Returns:
            UserResponse: 创建的用户信息

        Raises:
            HTTPException: 400 如果邮箱已被注册
        """
        email = data.email.lower()

        async with async_session_factory() as session:
            # Check email uniqueness
            result = await session.execute(
                text(
                    "SELECT 1 FROM users "
                    "WHERE email = :email AND is_deleted = false LIMIT 1"
                ),
                {"email": email},
            )
            if result.fetchone() is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该邮箱已被注册",
                )

            # Hash password
            password_hash = bcrypt.hashpw(
                data.password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")

            # Insert user
            result = await session.execute(
                text(
                    "INSERT INTO users (email, password_hash, enterprise_id, role) "
                    "VALUES (:email, :password_hash, :enterprise_id, :role) "
                    "RETURNING id, email, role, is_active, created_at"
                ),
                {
                    "email": email,
                    "password_hash": password_hash,
                    "enterprise_id": tenant_id,
                    "role": data.role,
                },
            )
            row = result.fetchone()
            await session.commit()

        return _row_to_user_response(row)

    async def update_user(
        self, tenant_id: str, user_id: str, data: UserUpdateRequest
    ) -> UserResponse:
        """修改用户角色和/或启用状态。

        Args:
            tenant_id: 企业 ID
            user_id: 用户 ID
            data: 用户更新请求

        Returns:
            UserResponse: 更新后的用户信息

        Raises:
            HTTPException: 404 如果用户不存在或不属于该企业
        """
        async with async_session_factory() as session:
            # Verify user belongs to tenant
            result = await session.execute(
                text(
                    "SELECT id FROM users "
                    "WHERE id = :user_id AND enterprise_id = :tenant_id "
                    "AND is_deleted = false LIMIT 1"
                ),
                {"user_id": user_id, "tenant_id": tenant_id},
            )
            if result.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="用户不存在",
                )

            # Build update fields
            updates = []
            params: dict = {"user_id": user_id}

            if data.role is not None:
                updates.append("role = :role")
                params["role"] = data.role

            if data.is_active is not None:
                updates.append("is_active = :is_active")
                params["is_active"] = data.is_active

            if updates:
                updates.append("updated_at = NOW()")
                set_clause = ", ".join(updates)
                await session.execute(
                    text(f"UPDATE users SET {set_clause} WHERE id = :user_id"),
                    params,
                )

            # Fetch updated user
            result = await session.execute(
                text(
                    "SELECT id, email, role, is_active, created_at "
                    "FROM users WHERE id = :user_id"
                ),
                {"user_id": user_id},
            )
            row = result.fetchone()
            await session.commit()

        return _row_to_user_response(row)

    async def delete_user(self, tenant_id: str, user_id: str) -> None:
        """软删除用户。

        Args:
            tenant_id: 企业 ID
            user_id: 用户 ID

        Raises:
            HTTPException: 404 如果用户不存在或不属于该企业
        """
        async with async_session_factory() as session:
            # Verify user belongs to tenant
            result = await session.execute(
                text(
                    "SELECT id FROM users "
                    "WHERE id = :user_id AND enterprise_id = :tenant_id "
                    "AND is_deleted = false LIMIT 1"
                ),
                {"user_id": user_id, "tenant_id": tenant_id},
            )
            if result.fetchone() is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="用户不存在",
                )

            # Soft delete
            await session.execute(
                text(
                    "UPDATE users SET is_deleted = true, updated_at = NOW() "
                    "WHERE id = :user_id"
                ),
                {"user_id": user_id},
            )
            await session.commit()

    async def batch_import(
        self, tenant_id: str, file_content: bytes, file_type: str
    ) -> BatchImportResult:
        """批量导入用户。

        解析 Excel (.xlsx) 或 CSV 文件，逐行验证并创建用户。

        Expected columns: email, password, role (optional, default 'member').

        Args:
            tenant_id: 企业 ID
            file_content: 文件二进制内容
            file_type: 文件类型 ("xlsx" 或 "csv")

        Returns:
            BatchImportResult: 导入结果摘要
        """
        # 1. Parse rows from file
        rows: list[dict[str, str]] = []
        errors: list[BatchImportError] = []

        if file_type == "xlsx":
            rows, errors = self._parse_xlsx(file_content)
        elif file_type == "csv":
            rows, errors = self._parse_csv(file_content)
        else:
            return BatchImportResult(
                success_count=0,
                failure_count=1,
                errors=[BatchImportError(row=0, reason=f"不支持的文件类型: {file_type}")],
            )

        # 2. Enforce max rows limit
        if len(rows) > _MAX_IMPORT_ROWS:
            return BatchImportResult(
                success_count=0,
                failure_count=0,
                errors=[
                    BatchImportError(
                        row=0,
                        reason=f"导入行数超过限制，最多 {_MAX_IMPORT_ROWS} 行",
                    )
                ],
            )

        # 3. Validate and insert rows
        success_count = 0

        async with async_session_factory() as session:
            for idx, row_data in enumerate(rows):
                row_num = idx + 2  # 1-based, skip header row

                email = (row_data.get("email") or "").strip().lower()
                password = (row_data.get("password") or "").strip()
                role = (row_data.get("role") or "member").strip().lower()

                # Validate email
                if not email or not _EMAIL_PATTERN.match(email):
                    errors.append(
                        BatchImportError(row=row_num, reason="邮箱格式无效")
                    )
                    continue

                # Validate password
                if len(password) < 8:
                    errors.append(
                        BatchImportError(row=row_num, reason="密码长度不足8位")
                    )
                    continue

                # Validate role
                if role not in ("admin", "member"):
                    role = "member"

                # Check email uniqueness
                result = await session.execute(
                    text(
                        "SELECT 1 FROM users "
                        "WHERE email = :email AND is_deleted = false LIMIT 1"
                    ),
                    {"email": email},
                )
                if result.fetchone() is not None:
                    errors.append(
                        BatchImportError(row=row_num, reason="邮箱已存在")
                    )
                    continue

                # Hash password and insert
                password_hash = bcrypt.hashpw(
                    password.encode("utf-8"), bcrypt.gensalt()
                ).decode("utf-8")

                await session.execute(
                    text(
                        "INSERT INTO users (email, password_hash, enterprise_id, role) "
                        "VALUES (:email, :password_hash, :enterprise_id, :role)"
                    ),
                    {
                        "email": email,
                        "password_hash": password_hash,
                        "enterprise_id": tenant_id,
                        "role": role,
                    },
                )
                success_count += 1

            await session.commit()

        return BatchImportResult(
            success_count=success_count,
            failure_count=len(errors),
            errors=errors,
        )

    @staticmethod
    def _parse_xlsx(
        file_content: bytes,
    ) -> tuple[list[dict[str, str]], list[BatchImportError]]:
        """Parse an Excel .xlsx file into row dicts."""
        import openpyxl

        errors: list[BatchImportError] = []
        rows: list[dict[str, str]] = []

        try:
            wb = openpyxl.load_workbook(io.BytesIO(file_content), read_only=True)
        except Exception:
            return [], [BatchImportError(row=0, reason="无法解析 Excel 文件")]

        ws = wb.active
        if ws is None:
            return [], [BatchImportError(row=0, reason="Excel 文件无活动工作表")]

        header: list[str] = []
        for row_idx, row in enumerate(ws.iter_rows(values_only=True)):
            if row_idx == 0:
                header = [str(c).strip().lower() if c else "" for c in row]
                continue
            row_dict: dict[str, str] = {}
            for col_idx, cell in enumerate(row):
                if col_idx < len(header) and header[col_idx]:
                    row_dict[header[col_idx]] = str(cell) if cell is not None else ""
            # Skip completely empty rows
            if any(v.strip() for v in row_dict.values()):
                rows.append(row_dict)

        wb.close()
        return rows, errors

    @staticmethod
    def _parse_csv(
        file_content: bytes,
    ) -> tuple[list[dict[str, str]], list[BatchImportError]]:
        """Parse a CSV file into row dicts."""
        errors: list[BatchImportError] = []
        rows: list[dict[str, str]] = []

        try:
            text_content = file_content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text_content = file_content.decode("gbk")
            except Exception:
                return [], [BatchImportError(row=0, reason="无法解码 CSV 文件")]

        reader = csv.DictReader(io.StringIO(text_content))
        for row_data in reader:
            # Normalize keys to lowercase
            normalized = {k.strip().lower(): v for k, v in row_data.items() if k}
            if any(v.strip() for v in normalized.values()):
                rows.append(normalized)

        return rows, errors
