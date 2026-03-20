"""LLM 客户端服务。

OpenAI 兼容 API 客户端，httpx 异步调用，支持流式响应和 429 重试逻辑。
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncGenerator, List, Optional

import httpx

from src.interview.llm_config_service import LLMConfigService
from src.interview.llm_models import LLMServiceError

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


class LLMClient:
    """OpenAI 兼容 API 客户端，httpx 异步，支持流式和重试。"""

    def __init__(self, config_service: LLMConfigService) -> None:
        self._config_service = config_service
        self._http = httpx.AsyncClient(timeout=60)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_request_params(
        self,
        tenant_id: str,
        messages: List[dict],
        temperature: Optional[float],
        max_tokens: Optional[int],
    ) -> tuple[str, dict, dict]:
        """Load tenant config and build URL, headers, payload.

        Returns (url, headers, payload).
        Raises LLMNotConfiguredError if no config available.
        """
        config = await self._config_service.get_effective_config(tenant_id)

        url = f"{config['base_url'].rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": config["model_name"],
            "messages": messages,
        }

        temp = temperature if temperature is not None else config.get("temperature")
        if temp is not None:
            payload["temperature"] = temp

        mt = max_tokens if max_tokens is not None else config.get("max_tokens")
        if mt is not None:
            payload["max_tokens"] = mt

        return url, headers, payload

    @staticmethod
    def _parse_retry_after(response: httpx.Response) -> float:
        """Extract wait seconds from Retry-After header (default 1s)."""
        raw = response.headers.get("Retry-After", "1")
        try:
            return float(raw)
        except (ValueError, TypeError):
            return 1.0

    @staticmethod
    def _raise_for_error(response: httpx.Response) -> None:
        """Raise LLMServiceError for non-2xx, non-429 responses."""
        if 200 <= response.status_code < 300:
            return
        if response.status_code == 429:
            return
        try:
            body = response.json()
            message = body.get("error", {}).get("message", response.text)
        except Exception:
            message = response.text
        raise LLMServiceError(status_code=response.status_code, message=message)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def chat_completion(
        self,
        tenant_id: str,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """发送聊天补全请求，返回完整响应文本。

        429 时读取 Retry-After 头等待后重试，最多重试 MAX_RETRIES 次。
        非 2xx 非 429 时抛出 LLMServiceError。
        未配置时抛出 LLMNotConfiguredError（由 get_effective_config 抛出）。
        """
        url, headers, payload = await self._get_request_params(
            tenant_id, messages, temperature, max_tokens,
        )

        retries = 0
        while True:
            resp = await self._http.post(url, json=payload, headers=headers)

            # Handle 429 with retry
            if resp.status_code == 429 and retries < MAX_RETRIES:
                wait = self._parse_retry_after(resp)
                logger.warning(
                    "LLM rate limited (429), retry %d/%d after %.1fs",
                    retries + 1, MAX_RETRIES, wait,
                )
                await asyncio.sleep(wait)
                retries += 1
                continue

            # After exhausting retries on 429, raise
            if resp.status_code == 429:
                raise LLMServiceError(
                    status_code=429,
                    message="速率限制，重试次数已用尽",
                )

            # Non-2xx non-429 → raise
            self._raise_for_error(resp)

            # Success — extract text
            data = resp.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as exc:
                raise LLMServiceError(
                    status_code=resp.status_code,
                    message=f"响应格式异常: {exc}",
                ) from exc

    async def chat_completion_stream(
        self,
        tenant_id: str,
        messages: List[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式聊天补全，逐块 yield 响应文本。

        429 时读取 Retry-After 头等待后重试，最多重试 MAX_RETRIES 次。
        非 2xx 非 429 时抛出 LLMServiceError。
        未配置时抛出 LLMNotConfiguredError。
        """
        url, headers, payload = await self._get_request_params(
            tenant_id, messages, temperature, max_tokens,
        )
        payload["stream"] = True

        retries = 0
        while True:
            resp = await self._http.send(
                self._http.build_request("POST", url, json=payload, headers=headers),
                stream=True,
            )

            if resp.status_code == 429 and retries < MAX_RETRIES:
                wait = self._parse_retry_after(resp)
                logger.warning(
                    "LLM stream rate limited (429), retry %d/%d after %.1fs",
                    retries + 1, MAX_RETRIES, wait,
                )
                await resp.aclose()
                await asyncio.sleep(wait)
                retries += 1
                continue

            if resp.status_code == 429:
                await resp.aclose()
                raise LLMServiceError(
                    status_code=429,
                    message="速率限制，重试次数已用尽",
                )

            if not (200 <= resp.status_code < 300):
                body = await resp.aread()
                await resp.aclose()
                try:
                    import json as _json
                    err = _json.loads(body)
                    message = err.get("error", {}).get("message", body.decode())
                except Exception:
                    message = body.decode() if isinstance(body, bytes) else str(body)
                raise LLMServiceError(
                    status_code=resp.status_code, message=message,
                )

            # Stream successful — yield chunks
            break

        try:
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[len("data: "):]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    import json as _json
                    chunk = _json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content
                except Exception:
                    continue
        finally:
            await resp.aclose()

    # ------------------------------------------------------------------
    # Message list builder (used by SessionManager)
    # ------------------------------------------------------------------

    @staticmethod
    def build_messages(
        system_prompt: str,
        history: List[dict],
        user_message: str,
    ) -> List[dict]:
        """构建消息列表：system + history + user。

        Returns list of {"role": ..., "content": ...} dicts.
        """
        msgs: List[dict] = [{"role": "system", "content": system_prompt}]
        msgs.extend(history)
        msgs.append({"role": "user", "content": user_message})
        return msgs
