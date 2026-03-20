"""Enterprise management service.

Provides methods for creating enterprises, querying by code,
and disabling enterprises.
"""

from __future__ import annotations

import random
import string

from sqlalchemy import text

from src.interview.db import async_session_factory


def _generate_enterprise_code() -> str:
    """Generate a unique enterprise code: 'ENT' + 6 random uppercase alphanumeric chars."""
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(random.choices(chars, k=6))
    return f"ENT{suffix}"


class EnterpriseService:
    """企业管理服务，负责企业的创建、查询与禁用。"""

    async def create_enterprise(self, name: str, domain: str) -> dict:
        """创建企业。

        生成唯一企业号，存储企业信息。

        Args:
            name: 企业名称
            domain: 企业邮箱域名

        Returns:
            dict: 包含 id, name, code, domain, status 的企业信息
        """
        async with async_session_factory() as session:
            # Generate a unique code, retry on collision
            for _ in range(10):
                code = _generate_enterprise_code()
                existing = await session.execute(
                    text("SELECT 1 FROM enterprises WHERE code = :code LIMIT 1"),
                    {"code": code},
                )
                if existing.fetchone() is None:
                    break
            else:
                raise RuntimeError("Failed to generate unique enterprise code")

            result = await session.execute(
                text(
                    "INSERT INTO enterprises (name, code, domain, status) "
                    "VALUES (:name, :code, :domain, 'active') "
                    "RETURNING id, name, code, domain, status"
                ),
                {"name": name, "code": code, "domain": domain},
            )
            row = result.fetchone()
            await session.commit()

        return {
            "id": str(row[0]),
            "name": row[1],
            "code": row[2],
            "domain": row[3],
            "status": row[4],
        }

    async def get_enterprise_by_code(self, code: str) -> dict | None:
        """按企业号查询企业。

        Args:
            code: 企业号

        Returns:
            dict | None: 企业信息字典，不存在时返回 None
        """
        async with async_session_factory() as session:
            result = await session.execute(
                text(
                    "SELECT id, name, code, domain, status "
                    "FROM enterprises WHERE code = :code LIMIT 1"
                ),
                {"code": code},
            )
            row = result.fetchone()

        if row is None:
            return None

        return {
            "id": str(row[0]),
            "name": row[1],
            "code": row[2],
            "domain": row[3],
            "status": row[4],
        }

    async def disable_enterprise(self, enterprise_id: str) -> None:
        """禁用企业。

        Args:
            enterprise_id: 企业 ID
        """
        async with async_session_factory() as session:
            await session.execute(
                text(
                    "UPDATE enterprises SET status = 'disabled', "
                    "updated_at = NOW() "
                    "WHERE id = :enterprise_id"
                ),
                {"enterprise_id": enterprise_id},
            )
            await session.commit()
