"""User management router with JWT authentication and admin authorization.

Provides CRUD endpoints for user management and batch import,
all protected by admin-only access control.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile, status
from jose import JWTError, jwt

from src.interview.auth_models import (
    BatchImportError,
    BatchImportResult,
    PaginatedUsers,
    UserCreateRequest,
    UserResponse,
    UserUpdateRequest,
)
from src.interview.config import settings
from src.interview.user_service import UserService


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Extract and validate JWT from Authorization header.

    Expects a Bearer token in the Authorization header. Decodes the JWT
    using the shared secret and returns user claims.

    Returns:
        dict with user_id, tenant_id, role

    Raises:
        HTTPException: 401 on missing/invalid/expired token
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )

    token = authorization[len("Bearer "):]

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")
    role = payload.get("role")

    if not user_id or not tenant_id or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing required claims",
        )

    return {"user_id": user_id, "tenant_id": tenant_id, "role": role}


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Verify the current user has admin role.

    Args:
        current_user: User claims from get_current_user dependency

    Returns:
        dict with user_id, tenant_id, role

    Raises:
        HTTPException: 403 if user is not an admin
    """
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


user_router = APIRouter(prefix="/api/users", tags=["users"])

_user_service = UserService()


@user_router.get("", response_model=PaginatedUsers)
async def list_users(
    page: int = 1,
    size: int = 20,
    search: str = "",
    current_user: dict = Depends(require_admin),
) -> PaginatedUsers:
    """查询用户列表（Admin 权限）。

    Args:
        page: 页码（从 1 开始）
        size: 每页数量
        search: 可选的邮箱搜索关键词
        current_user: 当前管理员用户

    Returns:
        PaginatedUsers: 分页用户列表
    """
    return await _user_service.list_users(
        tenant_id=current_user["tenant_id"],
        page=page,
        size=size,
        search=search if search else None,
    )


@user_router.post("", response_model=UserResponse)
async def create_user(
    data: UserCreateRequest,
    current_user: dict = Depends(require_admin),
) -> UserResponse:
    """创建用户（Admin 权限）。

    Args:
        data: 用户创建请求
        current_user: 当前管理员用户

    Returns:
        UserResponse: 创建的用户信息
    """
    return await _user_service.create_user(
        tenant_id=current_user["tenant_id"],
        data=data,
    )


@user_router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    data: UserUpdateRequest,
    current_user: dict = Depends(require_admin),
) -> UserResponse:
    """修改用户（Admin 权限）。

    Args:
        user_id: 用户 ID
        data: 用户更新请求
        current_user: 当前管理员用户

    Returns:
        UserResponse: 更新后的用户信息
    """
    return await _user_service.update_user(
        tenant_id=current_user["tenant_id"],
        user_id=user_id,
        data=data,
    )


@user_router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    current_user: dict = Depends(require_admin),
) -> dict:
    """删除用户（Admin 权限，软删除）。

    Args:
        user_id: 用户 ID
        current_user: 当前管理员用户

    Returns:
        dict: 删除确认消息
    """
    await _user_service.delete_user(
        tenant_id=current_user["tenant_id"],
        user_id=user_id,
    )
    return {"detail": "用户已删除"}


@user_router.post("/batch-import", response_model=BatchImportResult)
async def batch_import(
    file: UploadFile,
    current_user: dict = Depends(require_admin),
) -> BatchImportResult:
    """批量导入用户（Admin 权限）。

    支持 .xlsx 和 .csv 格式文件。

    Args:
        file: 上传的文件
        current_user: 当前管理员用户

    Returns:
        BatchImportResult: 导入结果摘要
    """
    # Determine file type from filename extension
    filename = file.filename or ""
    if filename.endswith(".xlsx"):
        file_type = "xlsx"
    elif filename.endswith(".csv"):
        file_type = "csv"
    else:
        return BatchImportResult(
            success_count=0,
            failure_count=1,
            errors=[BatchImportError(row=0, reason="不支持的文件格式，请上传 .xlsx 或 .csv 文件")],
        )

    file_content = await file.read()

    return await _user_service.batch_import(
        tenant_id=current_user["tenant_id"],
        file_content=file_content,
        file_type=file_type,
    )
