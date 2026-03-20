"""File management router — upload, list, download.

- Any authenticated user can upload files
- Admins can list and download all files across tenants
- Regular users can only see their own tenant's files
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from jose import JWTError, jwt

from src.interview.config import settings
from src.interview.file_storage import (
    FileStorageService,
    SUPPORTED_EXTENSIONS,
    get_category,
)
from src.interview.router import oauth2_scheme
from src.interview.db import async_session_factory
from sqlalchemy import text

file_router = APIRouter(prefix="/api/files", tags=["files"])

_storage = FileStorageService()


# ---------------------------------------------------------------------------
# Auth helper — extracts full user info from JWT
# ---------------------------------------------------------------------------

async def _get_user_info(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {
        "user_id": payload.get("user_id", ""),
        "tenant_id": payload.get("tenant_id", ""),
        "role": payload.get("role", "member"),
    }


# ---------------------------------------------------------------------------
# Upload endpoint — any authenticated user
# ---------------------------------------------------------------------------

@file_router.post("/upload")
async def upload_file(file: UploadFile, user: dict = Depends(_get_user_info)):
    """Upload any supported file type."""
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的文件格式: .{ext}",
        )

    content = await file.read()
    stored = _storage.save_file(
        content=content,
        original_name=filename,
        ext=ext,
        tenant_id=user["tenant_id"],
        uploaded_by=user["user_id"],
        content_type=file.content_type or "",
    )

    # Save metadata to DB
    async with async_session_factory() as session:
        await session.execute(
            text("""
                INSERT INTO uploaded_files
                    (id, original_name, stored_path, size_bytes, extension, category, content_type, uploaded_by, tenant_id, created_at)
                VALUES
                    (:id, :original_name, :stored_path, :size_bytes, :extension, :category, :content_type, :uploaded_by, :tenant_id, :created_at)
            """),
            {
                "id": stored.id,
                "original_name": stored.original_name,
                "stored_path": stored.stored_path,
                "size_bytes": stored.size_bytes,
                "extension": stored.extension,
                "category": stored.category,
                "content_type": stored.content_type,
                "uploaded_by": stored.uploaded_by,
                "tenant_id": stored.tenant_id,
                "created_at": stored.created_at,
            },
        )
        await session.commit()

    return {
        "id": stored.id,
        "file_name": stored.original_name,
        "size_bytes": stored.size_bytes,
        "category": stored.category,
        "created_at": stored.created_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# List files — admin sees all, member sees own tenant
# ---------------------------------------------------------------------------

@file_router.get("/list")
async def list_files(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: str | None = None,
    search: str | None = None,
    user: dict = Depends(_get_user_info),
):
    """List uploaded files with pagination and filters."""
    conditions = []
    params: dict = {"limit": size, "offset": (page - 1) * size}

    # Admin sees all tenants, member sees own only
    if user["role"] != "admin":
        conditions.append("tenant_id = :tenant_id")
        params["tenant_id"] = user["tenant_id"]

    if category:
        conditions.append("category = :category")
        params["category"] = category

    if search:
        conditions.append("original_name ILIKE :search")
        params["search"] = f"%{search}%"

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    async with async_session_factory() as session:
        count_result = await session.execute(
            text(f"SELECT COUNT(*) FROM uploaded_files {where}"), params
        )
        total = count_result.scalar() or 0

        rows = await session.execute(
            text(f"""
                SELECT id, original_name, size_bytes, extension, category,
                       uploaded_by, tenant_id, created_at, baidu_pan_fs_id, baidu_pan_path
                FROM uploaded_files {where}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            params,
        )
        items = [dict(r._mapping) for r in rows]

    # Convert datetime to string
    for item in items:
        if item.get("created_at"):
            item["created_at"] = item["created_at"].isoformat()

    return {"items": items, "total": total, "page": page, "size": size}


# ---------------------------------------------------------------------------
# Download file
# ---------------------------------------------------------------------------

@file_router.get("/download/{file_id}")
async def download_file(file_id: str, user: dict = Depends(_get_user_info)):
    """Download a file by ID."""
    async with async_session_factory() as session:
        result = await session.execute(
            text("SELECT stored_path, original_name, tenant_id FROM uploaded_files WHERE id = :id"),
            {"id": file_id},
        )
        row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="文件不存在")

    # Non-admin can only download own tenant's files
    if user["role"] != "admin" and row.tenant_id != user["tenant_id"]:
        raise HTTPException(status_code=403, detail="无权下载此文件")

    file_path = _storage.get_file_path(row.stored_path)
    if not file_path:
        raise HTTPException(status_code=404, detail="文件已被删除")

    return FileResponse(
        path=str(file_path),
        filename=row.original_name,
        media_type="application/octet-stream",
    )
