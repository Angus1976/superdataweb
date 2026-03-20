"""Baidu Pan (百度网盘) integration service.

Implements OAuth2 authorization code flow and file upload/list/download
via Baidu Pan Open API (个人版).

API Reference: https://pan.baidu.com/union/doc/
Upload flow: precreate → superfile upload → create (merge)

Keys are loaded dynamically from DB per tenant (admin configures via frontend).
Env vars serve as fallback defaults only.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from urllib.parse import quote

import httpx

# ---------------------------------------------------------------------------
# Fallback defaults from env (used when no DB config exists)
# ---------------------------------------------------------------------------

DEFAULT_APP_KEY = os.environ.get("BAIDU_PAN_APP_KEY", "")
DEFAULT_SECRET_KEY = os.environ.get("BAIDU_PAN_SECRET_KEY", "")
DEFAULT_REDIRECT_URI = os.environ.get("BAIDU_PAN_REDIRECT_URI", "http://localhost:8011/api/baidu-pan/callback")
DEFAULT_APP_DIR = os.environ.get("BAIDU_PAN_APP_DIR", "/apps/SuperInsight")

BAIDU_AUTH_URL = "https://openapi.baidu.com/oauth/2.0/authorize"
BAIDU_TOKEN_URL = "https://openapi.baidu.com/oauth/2.0/token"
BAIDU_PAN_API = "https://pan.baidu.com/rest/2.0/xpan"
BAIDU_PCS_API = "https://d.pcs.baidu.com/rest/2.0/pcs"

SLICE_SIZE = 4 * 1024 * 1024  # 4MB per slice


@dataclass
class BaiduPanConfig:
    """Per-tenant Baidu Pan API configuration."""
    app_key: str
    secret_key: str
    redirect_uri: str = DEFAULT_REDIRECT_URI
    app_dir: str = DEFAULT_APP_DIR


@dataclass
class BaiduTokenInfo:
    access_token: str
    refresh_token: str
    expires_in: int
    scope: str


class BaiduPanService:
    """Baidu Pan API client. All methods accept a config param for per-tenant keys."""

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=60, headers={"User-Agent": "pan.baidu.com"})

    # ------------------------------------------------------------------
    # OAuth2 Authorization Code Flow
    # ------------------------------------------------------------------

    def get_auth_url(self, cfg: BaiduPanConfig, state: str = "") -> str:
        """Generate the OAuth2 authorization URL for user to visit."""
        params = {
            "response_type": "code",
            "client_id": cfg.app_key,
            "redirect_uri": cfg.redirect_uri,
            "scope": "basic,netdisk",
            "display": "page",
        }
        if state:
            params["state"] = state
        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items())
        return f"{BAIDU_AUTH_URL}?{qs}"

    async def exchange_code(self, cfg: BaiduPanConfig, code: str) -> BaiduTokenInfo:
        """Exchange authorization code for access_token."""
        resp = await self._client.get(BAIDU_TOKEN_URL, params={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": cfg.app_key,
            "client_secret": cfg.secret_key,
            "redirect_uri": cfg.redirect_uri,
        })
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Baidu OAuth error: {data.get('error_description', data['error'])}")
        return BaiduTokenInfo(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
            scope=data.get("scope", ""),
        )

    async def refresh_token(self, cfg: BaiduPanConfig, refresh_token: str) -> BaiduTokenInfo:
        """Refresh an expired access_token."""
        resp = await self._client.get(BAIDU_TOKEN_URL, params={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": cfg.app_key,
            "client_secret": cfg.secret_key,
        })
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"Baidu refresh error: {data.get('error_description', data['error'])}")
        return BaiduTokenInfo(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
            scope=data.get("scope", ""),
        )

    # ------------------------------------------------------------------
    # User Info
    # ------------------------------------------------------------------

    async def get_user_info(self, access_token: str) -> dict:
        """Get Baidu Pan user info."""
        resp = await self._client.get(f"{BAIDU_PAN_API}/nas", params={
            "method": "uinfo",
            "access_token": access_token,
        })
        return resp.json()

    # ------------------------------------------------------------------
    # Connectivity test — verify app_key/secret_key are valid
    # ------------------------------------------------------------------

    async def test_connectivity(self, cfg: BaiduPanConfig) -> dict:
        """Test if the API key pair is valid by hitting the token endpoint.

        We use device_code grant to verify the app_key is recognized.
        Returns {"ok": True/False, "message": str}.
        """
        try:
            resp = await self._client.get(
                "https://openapi.baidu.com/oauth/2.0/device/code",
                params={
                    "response_type": "device_code",
                    "client_id": cfg.app_key,
                    "scope": "basic,netdisk",
                },
            )
            data = resp.json()
            if "device_code" in data:
                return {"ok": True, "message": "API Key 验证通过"}
            return {"ok": False, "message": data.get("error_description", "API Key 无效")}
        except Exception as e:
            return {"ok": False, "message": f"连接失败: {e}"}


    # ------------------------------------------------------------------
    # File Upload (precreate → superfile → create)
    # ------------------------------------------------------------------

    async def upload_file(
        self, access_token: str, file_content: bytes, remote_path: str
    ) -> dict:
        """Upload a file to Baidu Pan."""
        size = len(file_content)

        slices = []
        block_md5_list = []
        for i in range(0, size, SLICE_SIZE):
            chunk = file_content[i:i + SLICE_SIZE]
            slices.append(chunk)
            block_md5_list.append(hashlib.md5(chunk).hexdigest())

        content_md5 = hashlib.md5(file_content).hexdigest()
        slice_md5 = hashlib.md5(file_content[:256 * 1024]).hexdigest()

        # Step 1: Precreate
        precreate_resp = await self._client.post(
            f"{BAIDU_PAN_API}/file",
            params={"method": "precreate", "access_token": access_token},
            data={
                "path": remote_path,
                "size": str(size),
                "isdir": "0",
                "autoinit": "1",
                "rtype": "3",
                "block_list": json.dumps(block_md5_list),
                "content-md5": content_md5,
                "slice-md5": slice_md5,
            },
        )
        pre_data = precreate_resp.json()
        if pre_data.get("errno", -1) != 0:
            raise RuntimeError(f"Baidu precreate failed: errno={pre_data.get('errno')}")

        uploadid = pre_data["uploadid"]

        # Step 2: Upload each slice
        for idx, chunk in enumerate(slices):
            upload_resp = await self._client.post(
                f"{BAIDU_PCS_API}/superfile2",
                params={
                    "method": "upload",
                    "access_token": access_token,
                    "type": "tmpfile",
                    "path": remote_path,
                    "uploadid": uploadid,
                    "partseq": str(idx),
                },
                files={"file": ("chunk", chunk)},
            )
            up_data = upload_resp.json()
            if "md5" not in up_data:
                raise RuntimeError(f"Baidu slice upload failed at part {idx}: {up_data}")

        # Step 3: Create (merge)
        create_resp = await self._client.post(
            f"{BAIDU_PAN_API}/file",
            params={"method": "create", "access_token": access_token},
            data={
                "path": remote_path,
                "size": str(size),
                "isdir": "0",
                "rtype": "3",
                "uploadid": uploadid,
                "block_list": json.dumps(block_md5_list),
            },
        )
        create_data = create_resp.json()
        if create_data.get("errno", -1) != 0:
            raise RuntimeError(f"Baidu create failed: errno={create_data.get('errno')}")

        return create_data

    # ------------------------------------------------------------------
    # File List
    # ------------------------------------------------------------------

    async def list_files(
        self, access_token: str, dir_path: str, start: int = 0, limit: int = 100
    ) -> dict:
        """List files in a Baidu Pan directory."""
        resp = await self._client.get(f"{BAIDU_PAN_API}/file", params={
            "method": "list",
            "access_token": access_token,
            "dir": dir_path,
            "order": "time",
            "desc": "1",
            "start": str(start),
            "limit": str(limit),
            "web": "1",
        })
        return resp.json()

    # ------------------------------------------------------------------
    # File Download (get dlink)
    # ------------------------------------------------------------------

    async def get_download_link(self, access_token: str, fs_id: int) -> str:
        """Get download link for a file by fs_id."""
        resp = await self._client.get(f"{BAIDU_PAN_API}/multimedia", params={
            "method": "filemetas",
            "access_token": access_token,
            "fsids": json.dumps([fs_id]),
            "dlink": "1",
        })
        data = resp.json()
        if data.get("errno", -1) != 0:
            raise RuntimeError(f"Baidu filemetas failed: {data}")
        items = data.get("list", [])
        if not items:
            raise RuntimeError("File not found on Baidu Pan")
        dlink = items[0].get("dlink", "")
        return f"{dlink}&access_token={access_token}" if dlink else ""

    # ------------------------------------------------------------------
    # Share link transfer (转存分享链接到自己网盘)
    # ------------------------------------------------------------------

    async def transfer_shared_file(
        self, access_token: str, share_link: str, password: str, app_dir: str
    ) -> dict:
        """Transfer files from a Baidu Pan share link into the user's own Pan.

        Steps:
        1. Verify share link → get shareid, uk
        2. Get file list from share → get fs_ids
        3. Transfer to own Pan directory
        """
        # Extract surl from share link (e.g. https://pan.baidu.com/s/1xxxxx)
        surl = share_link.strip().rstrip("/")
        if "/s/" in surl:
            surl = surl.split("/s/")[-1]
        # Remove leading '1' if present (Baidu short URL convention)
        if surl.startswith("1"):
            surl = surl[1:]

        # Step 1: Verify share and get shareid/uk
        verify_resp = await self._client.post(
            "https://pan.baidu.com/rest/2.0/xpan/share",
            params={"method": "verify", "access_token": access_token},
            data={"surl": surl, "password": password},
        )
        verify_data = verify_resp.json()
        if verify_data.get("errno", -1) != 0:
            raise RuntimeError(f"分享链接验证失败: errno={verify_data.get('errno')}，请检查链接和提取码")

        randsk = verify_data.get("randsk", "")

        # Step 2: Get file list from share
        list_resp = await self._client.get(
            "https://pan.baidu.com/rest/2.0/xpan/share",
            params={
                "method": "list",
                "access_token": access_token,
                "surl": surl,
                "page": "1",
                "num": "100",
            },
            headers={"Cookie": f"BDCLND={randsk}"},
        )
        list_data = list_resp.json()
        if list_data.get("errno", -1) != 0:
            raise RuntimeError(f"获取分享文件列表失败: {list_data}")

        file_list = list_data.get("list", [])
        if not file_list:
            raise RuntimeError("分享链接中没有文件")

        shareid = list_data.get("shareid") or verify_data.get("shareid", 0)
        share_uk = list_data.get("uk") or verify_data.get("uk", 0)
        fs_ids = [f["fs_id"] for f in file_list]

        # Step 3: Transfer to own Pan
        transfer_resp = await self._client.post(
            "https://pan.baidu.com/rest/2.0/xpan/share",
            params={
                "method": "transfer",
                "access_token": access_token,
                "shareid": str(shareid),
                "from": str(share_uk),
            },
            data={
                "fsidlist": json.dumps(fs_ids),
                "path": app_dir,
            },
            headers={"Cookie": f"BDCLND={randsk}"},
        )
        transfer_data = transfer_resp.json()
        if transfer_data.get("errno", -1) != 0:
            raise RuntimeError(f"转存失败: errno={transfer_data.get('errno')}")

        return {
            "transferred_count": len(fs_ids),
            "files": [{"name": f.get("server_filename", ""), "size": f.get("size", 0)} for f in file_list],
            "target_dir": app_dir,
        }
