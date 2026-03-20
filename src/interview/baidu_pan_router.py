"""Baidu Pan (百度网盘) router — config, OAuth, upload, list, download, sync, share import.

Admin endpoints:
  POST /api/baidu-pan/config          — save API Key config
  GET  /api/baidu-pan/config          — get current config (masked)
  POST /api/baidu-pan/config/test     — test API Key connectivity
  GET  /api/baidu-pan/auth-url        — return OAuth URL
  GET  /api/baidu-pan/callback        — handle OAuth callback
  GET  /api/baidu-pan/status          — check connection status
  POST /api/baidu-pan/sync/{file_id}  — sync local file to Baidu Pan
  GET  /api/baidu-pan/files           — list files on Baidu Pan
  GET  /api/baidu-pan/download/{fs_id}— get download link
  DELETE /api/baidu-pan/disconnect    — disconnect
  POST /api/baidu-pan/import-share    — import from share link
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel
from sqlalchemy import text

from src.interview.baidu_pan import (
    BaiduPanConfig, BaiduPanService,
    DEFAULT_APP_DIR, DEFAULT_APP_KEY, DEFAULT_REDIRECT_URI, DEFAULT_SECRET_KEY,
)
from src.interview.config import settings
from src.interview.db import async_session_factory
from src.interview.file_storage import UPLOAD_DIR
from src.interview.router import oauth2_scheme

baidu_pan_router = APIRouter(prefix="/api/baidu-pan", tags=["baidu-pan"])

_svc = BaiduPanService()


# ---------------------------------------------------------------------------
# Auth helper
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


def _require_admin(user: dict) -> None:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可操作百度网盘")


# ---------------------------------------------------------------------------
# Config helpers — load per-tenant config from DB, fallback to env
# ---------------------------------------------------------------------------

async def _get_tenant_config(tenant_id: str) -> BaiduPanConfig:
    """Load Baidu Pan API config for a tenant from DB, fallback to env vars."""
    async with async_session_factory() as session:
        row = await session.execute(
            text("SELECT app_key, secret_key, app_dir, redirect_uri FROM baidu_pan_config WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        rec = row.first()
    if rec and rec.app_key:
        return BaiduPanConfig(
            app_key=rec.app_key,
            secret_key=rec.secret_key,
            app_dir=rec.app_dir or DEFAULT_APP_DIR,
            redirect_uri=rec.redirect_uri or DEFAULT_REDIRECT_URI,
        )
    # Fallback to env vars
    if DEFAULT_APP_KEY:
        return BaiduPanConfig(
            app_key=DEFAULT_APP_KEY,
            secret_key=DEFAULT_SECRET_KEY,
            redirect_uri=DEFAULT_REDIRECT_URI,
            app_dir=DEFAULT_APP_DIR,
        )
    raise HTTPException(status_code=400, detail="请先配置百度网盘 API Key")


async def _get_tenant_token(tenant_id: str) -> dict | None:
    """Get stored Baidu Pan OAuth token for a tenant, auto-refresh if expired."""
    cfg = await _get_tenant_config(tenant_id)
    async with async_session_factory() as session:
        row = await session.execute(
            text("SELECT access_token, refresh_token, expires_at FROM baidu_pan_tokens WHERE tenant_id = :tid"),
            {"tid": tenant_id},
        )
        rec = row.first()
    if not rec:
        return None

    access_token = rec.access_token
    refresh_token = rec.refresh_token
    expires_at = rec.expires_at

    # Auto-refresh if expired (5 min buffer)
    if expires_at < datetime.now(timezone.utc) + timedelta(minutes=5):
        try:
            info = await _svc.refresh_token(cfg, refresh_token)
            access_token = info.access_token
            refresh_token = info.refresh_token
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=info.expires_in)
            async with async_session_factory() as session:
                await session.execute(
                    text("""UPDATE baidu_pan_tokens
                            SET access_token = :at, refresh_token = :rt, expires_at = :ea, updated_at = NOW()
                            WHERE tenant_id = :tid"""),
                    {"at": access_token, "rt": refresh_token, "ea": expires_at, "tid": tenant_id},
                )
                await session.commit()
        except Exception:
            return None

    return {"access_token": access_token, "refresh_token": refresh_token, "expires_at": expires_at}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class BaiduConfigRequest(BaseModel):
    app_key: str
    secret_key: str
    app_dir: str = "/apps/SuperInsight"
    redirect_uri: str = "http://localhost:8011/api/baidu-pan/callback"


class ShareImportRequest(BaseModel):
    share_link: str
    password: str = ""


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------

@baidu_pan_router.post("/config")
async def save_config(body: BaiduConfigRequest, user: dict = Depends(_get_user_info)):
    """Save Baidu Pan API Key configuration for current tenant."""
    _require_admin(user)
    async with async_session_factory() as session:
        await session.execute(
            text("""INSERT INTO baidu_pan_config (tenant_id, app_key, secret_key, app_dir, redirect_uri)
                    VALUES (:tid, :ak, :sk, :ad, :ru)
                    ON CONFLICT (tenant_id) DO UPDATE
                    SET app_key = :ak, secret_key = :sk, app_dir = :ad, redirect_uri = :ru, updated_at = NOW()"""),
            {"tid": user["tenant_id"], "ak": body.app_key, "sk": body.secret_key,
             "ad": body.app_dir, "ru": body.redirect_uri},
        )
        await session.commit()
    return {"message": "配置已保存"}


@baidu_pan_router.get("/config")
async def get_config(user: dict = Depends(_get_user_info)):
    """Get current Baidu Pan config (secret_key masked)."""
    _require_admin(user)
    async with async_session_factory() as session:
        row = await session.execute(
            text("SELECT app_key, secret_key, app_dir, redirect_uri FROM baidu_pan_config WHERE tenant_id = :tid"),
            {"tid": user["tenant_id"]},
        )
        rec = row.first()
    if not rec:
        return {"configured": False}
    masked_sk = rec.secret_key[:4] + "****" + rec.secret_key[-4:] if len(rec.secret_key) > 8 else "****"
    return {
        "configured": True,
        "app_key": rec.app_key,
        "secret_key_masked": masked_sk,
        "app_dir": rec.app_dir,
        "redirect_uri": rec.redirect_uri,
    }


@baidu_pan_router.post("/config/test")
async def test_config(body: BaiduConfigRequest, user: dict = Depends(_get_user_info)):
    """Test Baidu Pan API Key connectivity."""
    _require_admin(user)
    cfg = BaiduPanConfig(
        app_key=body.app_key,
        secret_key=body.secret_key,
        app_dir=body.app_dir,
        redirect_uri=body.redirect_uri,
    )
    result = await _svc.test_connectivity(cfg)
    return result


# ---------------------------------------------------------------------------
# OAuth endpoints
# ---------------------------------------------------------------------------

@baidu_pan_router.get("/auth-url")
async def get_auth_url(user: dict = Depends(_get_user_info)):
    """Return Baidu Pan OAuth authorization URL."""
    _require_admin(user)
    cfg = await _get_tenant_config(user["tenant_id"])
    url = _svc.get_auth_url(cfg, state=user["tenant_id"])
    return {"auth_url": url}


@baidu_pan_router.get("/callback")
async def oauth_callback(code: str, state: str = ""):
    """Handle Baidu Pan OAuth callback."""
    tenant_id = state
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing state (tenant_id)")

    cfg = await _get_tenant_config(tenant_id)
    info = await _svc.exchange_code(cfg, code)
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=info.expires_in)

    user_info = await _svc.get_user_info(info.access_token)
    baidu_uk = user_info.get("uk", 0)
    baidu_name = user_info.get("baidu_name", "")

    async with async_session_factory() as session:
        await session.execute(
            text("""INSERT INTO baidu_pan_tokens (tenant_id, access_token, refresh_token, expires_at, baidu_uk, baidu_name)
                    VALUES (:tid, :at, :rt, :ea, :uk, :name)
                    ON CONFLICT (tenant_id) DO UPDATE
                    SET access_token = :at, refresh_token = :rt, expires_at = :ea,
                        baidu_uk = :uk, baidu_name = :name, updated_at = NOW()"""),
            {"tid": tenant_id, "at": info.access_token, "rt": info.refresh_token,
             "ea": expires_at, "uk": baidu_uk, "name": baidu_name},
        )
        await session.commit()

    return RedirectResponse(url="/admin/files?baidu_connected=1")


# ---------------------------------------------------------------------------
# Status / Disconnect
# ---------------------------------------------------------------------------

@baidu_pan_router.get("/status")
async def get_status(user: dict = Depends(_get_user_info)):
    """Check if current tenant has connected Baidu Pan."""
    _require_admin(user)
    # Check if config exists
    async with async_session_factory() as session:
        cfg_row = await session.execute(
            text("SELECT app_key FROM baidu_pan_config WHERE tenant_id = :tid"),
            {"tid": user["tenant_id"]},
        )
        has_config = cfg_row.first() is not None

        row = await session.execute(
            text("SELECT baidu_name, expires_at FROM baidu_pan_tokens WHERE tenant_id = :tid"),
            {"tid": user["tenant_id"]},
        )
        rec = row.first()

    if not rec:
        return {"connected": False, "configured": has_config}
    return {
        "connected": True,
        "configured": has_config,
        "baidu_name": rec.baidu_name,
        "expires_at": rec.expires_at.isoformat() if rec.expires_at else None,
    }


@baidu_pan_router.delete("/disconnect")
async def disconnect(user: dict = Depends(_get_user_info)):
    """Disconnect Baidu Pan for current tenant (keeps config)."""
    _require_admin(user)
    async with async_session_factory() as session:
        await session.execute(
            text("DELETE FROM baidu_pan_tokens WHERE tenant_id = :tid"),
            {"tid": user["tenant_id"]},
        )
        await session.commit()
    return {"message": "已断开百度网盘连接"}


# ---------------------------------------------------------------------------
# Sync / Files / Download
# ---------------------------------------------------------------------------

@baidu_pan_router.post("/sync/{file_id}")
async def sync_to_baidu_pan(file_id: str, user: dict = Depends(_get_user_info)):
    """Sync a locally uploaded file to Baidu Pan."""
    _require_admin(user)
    cfg = await _get_tenant_config(user["tenant_id"])
    token_info = await _get_tenant_token(user["tenant_id"])
    if not token_info:
        raise HTTPException(status_code=400, detail="请先授权百度网盘")

    async with async_session_factory() as session:
        row = await session.execute(
            text("SELECT stored_path, original_name, baidu_pan_fs_id FROM uploaded_files WHERE id = :id AND tenant_id = :tid"),
            {"id": file_id, "tid": user["tenant_id"]},
        )
        rec = row.first()

    if not rec:
        raise HTTPException(status_code=404, detail="文件不存在")
    if rec.baidu_pan_fs_id:
        return {"message": "文件已同步", "fs_id": rec.baidu_pan_fs_id}

    file_path = UPLOAD_DIR / rec.stored_path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="本地文件已被删除")

    content = file_path.read_bytes()
    remote_path = f"{cfg.app_dir}/{user['tenant_id']}/{rec.original_name}"

    result = await _svc.upload_file(token_info["access_token"], content, remote_path)
    fs_id = result.get("fs_id", 0)
    pan_path = result.get("path", remote_path)

    async with async_session_factory() as session:
        await session.execute(
            text("UPDATE uploaded_files SET baidu_pan_fs_id = :fsid, baidu_pan_path = :path WHERE id = :id"),
            {"fsid": fs_id, "path": pan_path, "id": file_id},
        )
        await session.commit()

    return {"message": "同步成功", "fs_id": fs_id, "path": pan_path}


@baidu_pan_router.get("/files")
async def list_baidu_files(
    dir_path: str = "",
    start: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    user: dict = Depends(_get_user_info),
):
    """List files on Baidu Pan."""
    _require_admin(user)
    cfg = await _get_tenant_config(user["tenant_id"])
    token_info = await _get_tenant_token(user["tenant_id"])
    if not token_info:
        raise HTTPException(status_code=400, detail="请先授权百度网盘")

    path = dir_path or f"{cfg.app_dir}/{user['tenant_id']}"
    return await _svc.list_files(token_info["access_token"], dir_path=path, start=start, limit=limit)


@baidu_pan_router.get("/download/{fs_id}")
async def get_download_link(fs_id: int, user: dict = Depends(_get_user_info)):
    """Get Baidu Pan download link for a file."""
    _require_admin(user)
    token_info = await _get_tenant_token(user["tenant_id"])
    if not token_info:
        raise HTTPException(status_code=400, detail="请先授权百度网盘")

    link = await _svc.get_download_link(token_info["access_token"], fs_id)
    if not link:
        raise HTTPException(status_code=404, detail="无法获取下载链接")
    return {"download_url": link}


# ---------------------------------------------------------------------------
# Share link import
# ---------------------------------------------------------------------------

@baidu_pan_router.post("/import-share")
async def import_share(body: ShareImportRequest, user: dict = Depends(_get_user_info)):
    """Import files from a Baidu Pan share link into the tenant's Pan directory."""
    _require_admin(user)
    cfg = await _get_tenant_config(user["tenant_id"])
    token_info = await _get_tenant_token(user["tenant_id"])
    if not token_info:
        raise HTTPException(status_code=400, detail="请先授权百度网盘")

    target_dir = f"{cfg.app_dir}/{user['tenant_id']}"
    result = await _svc.transfer_shared_file(
        token_info["access_token"], body.share_link, body.password, target_dir
    )
    return result
