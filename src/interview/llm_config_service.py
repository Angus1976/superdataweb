"""LLM 配置管理服务。

租户级 LLM 配置 CRUD，API Key Fernet 加密存储，环境变量回退，连通性测试。
遵循 baidu_pan.py 的服务模式：DB 配置 + 环境变量回退。
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from typing import Dict, Optional

import httpx
from cryptography.fernet import Fernet

from src.interview.config import settings
from src.interview.llm_models import (
    ConnectivityResult,
    LLMConfigRequest,
    LLMConfigResponse,
    LLMNotConfiguredError,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory storage (mirrors baidu_pan.py pattern; swap for real DB later)
# ---------------------------------------------------------------------------

_llm_config_store: Dict[str, dict] = {}


class LLMConfigService:
    """租户级 LLM 配置 CRUD，API Key 加密存储，环境变量回退。"""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=15)

    # ------------------------------------------------------------------
    # Encryption helpers
    # ------------------------------------------------------------------

    def _get_fernet(self) -> Fernet:
        """Derive a Fernet instance from LLM_ENCRYPTION_KEY env or JWT_SECRET."""
        raw_key = os.environ.get("LLM_ENCRYPTION_KEY") or settings.JWT_SECRET
        if not raw_key:
            raise ValueError("加密密钥未配置：请设置 LLM_ENCRYPTION_KEY 或 JWT_SECRET")
        # Derive a 32-byte key via SHA-256, then base64-encode for Fernet
        derived = hashlib.sha256(raw_key.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(derived)
        return Fernet(fernet_key)

    def encrypt_api_key(self, api_key: str) -> str:
        """使用 Fernet 对称加密 API Key。"""
        f = self._get_fernet()
        return f.encrypt(api_key.encode()).decode()

    def decrypt_api_key(self, encrypted: str) -> str:
        """解密 API Key。"""
        f = self._get_fernet()
        return f.decrypt(encrypted.encode()).decode()

    def mask_api_key(self, api_key: str) -> str:
        """掩码显示：前4位 + **** + 后4位；长度 ≤ 8 返回 ****。"""
        if len(api_key) <= 8:
            return "****"
        return api_key[:4] + "****" + api_key[-4:]

    # ------------------------------------------------------------------
    # CRUD — in-memory dict (swap for DB later)
    # ------------------------------------------------------------------

    async def save_config(self, tenant_id: str, req: LLMConfigRequest) -> LLMConfigResponse:
        """UPSERT 保存配置，api_key 加密后存储。"""
        encrypted_key = self.encrypt_api_key(req.api_key)
        _llm_config_store[tenant_id] = {
            "provider_name": req.provider_name,
            "encrypted_api_key": encrypted_key,
            "base_url": req.base_url,
            "model_name": req.model_name,
            "temperature": req.temperature,
            "max_tokens": req.max_tokens,
        }
        return LLMConfigResponse(
            configured=True,
            provider_name=req.provider_name,
            api_key_masked=self.mask_api_key(req.api_key),
            base_url=req.base_url,
            model_name=req.model_name,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
        )

    async def get_config(self, tenant_id: str) -> LLMConfigResponse:
        """读取 DB 配置，api_key 返回掩码。无配置时返回 configured=False。"""
        rec = _llm_config_store.get(tenant_id)
        if not rec:
            return LLMConfigResponse(configured=False)
        decrypted_key = self.decrypt_api_key(rec["encrypted_api_key"])
        return LLMConfigResponse(
            configured=True,
            provider_name=rec["provider_name"],
            api_key_masked=self.mask_api_key(decrypted_key),
            base_url=rec["base_url"],
            model_name=rec["model_name"],
            temperature=rec["temperature"],
            max_tokens=rec["max_tokens"],
        )

    async def get_config_decrypted(self, tenant_id: str) -> Optional[dict]:
        """读取 DB 配置，api_key 解密返回（仅内部使用）。无配置时返回 None。"""
        rec = _llm_config_store.get(tenant_id)
        if not rec:
            return None
        return {
            "provider_name": rec["provider_name"],
            "api_key": self.decrypt_api_key(rec["encrypted_api_key"]),
            "base_url": rec["base_url"],
            "model_name": rec["model_name"],
            "temperature": rec["temperature"],
            "max_tokens": rec["max_tokens"],
        }

    async def get_effective_config(self, tenant_id: str) -> dict:
        """获取有效配置：优先 DB，回退环境变量。无配置时抛 LLMNotConfiguredError。"""
        # Priority 1: DB config
        decrypted = await self.get_config_decrypted(tenant_id)
        if decrypted:
            return decrypted

        # Priority 2: Environment variables
        env_api_key = os.environ.get("LLM_API_KEY", "")
        if env_api_key:
            return {
                "provider_name": "env",
                "api_key": env_api_key,
                "base_url": os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
                "model_name": os.environ.get("LLM_MODEL_NAME", "gpt-3.5-turbo"),
                "temperature": float(os.environ.get("LLM_TEMPERATURE", "0.7")),
                "max_tokens": int(os.environ.get("LLM_MAX_TOKENS", "2048")),
            }

        raise LLMNotConfiguredError()

    # ------------------------------------------------------------------
    # Connectivity test
    # ------------------------------------------------------------------

    async def test_connectivity(self, req: LLMConfigRequest) -> ConnectivityResult:
        """使用提供的配置参数测试 LLM 服务连通性。

        向 {base_url}/chat/completions 发送一条简短的 "你好" 测试消息。
        """
        url = f"{req.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {req.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": req.model_name,
            "messages": [{"role": "user", "content": "你好"}],
            "max_tokens": 16,
        }

        start_ts = time.monotonic()
        try:
            resp = await self._http.post(url, json=payload, headers=headers)
            elapsed_ms = int((time.monotonic() - start_ts) * 1000)

            if resp.status_code in (401, 403):
                return ConnectivityResult(
                    ok=False,
                    message="API Key 无效或无权限",
                )

            if resp.status_code >= 400:
                return ConnectivityResult(
                    ok=False,
                    message=f"服务返回错误: HTTP {resp.status_code}",
                )

            data = resp.json()
            model = data.get("model", req.model_name)
            return ConnectivityResult(
                ok=True,
                message="连接成功",
                model=model,
                response_time_ms=elapsed_ms,
            )

        except httpx.TimeoutException:
            return ConnectivityResult(
                ok=False,
                message="连接超时，请检查 Base URL 是否正确",
            )
        except httpx.ConnectError:
            return ConnectivityResult(
                ok=False,
                message="连接超时，请检查 Base URL 是否正确",
            )
        except Exception as exc:
            logger.error("LLM connectivity test failed: %s", exc)
            return ConnectivityResult(
                ok=False,
                message=f"连接失败: {exc}",
            )
