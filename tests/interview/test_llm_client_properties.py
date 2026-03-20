"""Property-based tests for LLMClient.

Property 7: LLM 错误状态码映射 — 对任意非 2xx 非 429 HTTP 状态码，
LLMClient.chat_completion 应抛出 LLMServiceError 且包含正确状态码。

**Validates: Requirements 6.5**
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from hypothesis import given, settings as h_settings, strategies as st

from src.interview.llm_client import LLMClient
from src.interview.llm_config_service import LLMConfigService
from src.interview.llm_models import LLMServiceError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FAKE_CONFIG: dict = {
    "provider_name": "openai",
    "api_key": "sk-test-key-123",
    "base_url": "https://api.example.com/v1",
    "model_name": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2048,
}

# All valid HTTP status codes that are non-2xx AND non-429
_NON_2XX_NON_429_CODES = (
    list(range(100, 200))    # 1xx informational
    + list(range(300, 429))  # 3xx + 4xx up to 428
    + list(range(430, 512))  # 4xx from 430 + 5xx
)


# ---------------------------------------------------------------------------
# Property 7: LLM 错误状态码映射
# ---------------------------------------------------------------------------


class TestLLMErrorStatusCodeMapping:
    """# Feature: llm-config-management, Property 7: LLM 错误状态码映射

    For any HTTP status code that is non-2xx and non-429, calling
    LLMClient.chat_completion must raise LLMServiceError with the
    matching status_code attribute.

    **Validates: Requirements 6.5**
    """

    @given(status_code=st.sampled_from(_NON_2XX_NON_429_CODES))
    @h_settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_non_2xx_non_429_raises_llm_service_error(self, status_code: int) -> None:
        """# Feature: llm-config-management, Property 7: LLM 错误状态码映射

        A random non-2xx non-429 status code from the LLM provider must
        cause chat_completion to raise LLMServiceError with the correct
        status_code."""
        # Setup: mock config service to return valid config
        config_svc = LLMConfigService()
        config_svc.get_effective_config = AsyncMock(return_value=FAKE_CONFIG)
        client = LLMClient(config_svc)

        # Build a mock httpx.Response with the generated status code
        error_body = {"error": {"message": f"error {status_code}"}}
        mock_response = httpx.Response(status_code, json=error_body)

        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(LLMServiceError) as exc_info:
                await client.chat_completion(
                    "tenant-1",
                    [{"role": "user", "content": "hello"}],
                )

            assert exc_info.value.status_code == status_code


# ---------------------------------------------------------------------------
# Strategies for Property 8
# ---------------------------------------------------------------------------

def _history_messages(draw: st.DrawFn) -> list[dict]:
    """Generate a list of alternating user/assistant history messages."""
    n = draw(st.integers(min_value=0, max_value=20))
    messages: list[dict] = []
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        content = draw(st.text(min_size=1, max_size=100))
        messages.append({"role": role, "content": content})
    return messages


history_strategy = st.composite(_history_messages)


# ---------------------------------------------------------------------------
# Property 8: 消息列表构建顺序
# ---------------------------------------------------------------------------


class TestMessageListBuildOrder:
    """# Feature: llm-config-management, Property 8: 消息列表构建顺序

    For any system_prompt, history message list (alternating user/assistant),
    and current user message, the built message list must satisfy:
    - First message: role="system", content=system_prompt
    - Middle messages: match history in order
    - Last message: role="user", content=user_message
    - Total length = 1 + len(history) + 1

    **Validates: Requirements 7.2**
    """

    @given(
        system_prompt=st.text(min_size=0, max_size=200),
        history=history_strategy(),
        user_message=st.text(min_size=1, max_size=200),
    )
    @h_settings(max_examples=100, deadline=None)
    def test_build_messages_structure(
        self,
        system_prompt: str,
        history: list[dict],
        user_message: str,
    ) -> None:
        """# Feature: llm-config-management, Property 8: 消息列表构建顺序

        Verify that build_messages produces the correct structure:
        system + history + user, with total length = 1 + len(history) + 1."""
        result = LLMClient.build_messages(system_prompt, history, user_message)

        # Total length = 1 (system) + len(history) + 1 (user)
        assert len(result) == 1 + len(history) + 1

        # First message is system with correct content
        assert result[0]["role"] == "system"
        assert result[0]["content"] == system_prompt

        # Middle messages match history in order
        for i, hist_msg in enumerate(history):
            assert result[i + 1]["role"] == hist_msg["role"]
            assert result[i + 1]["content"] == hist_msg["content"]

        # Last message is user with correct content
        assert result[-1]["role"] == "user"
        assert result[-1]["content"] == user_message
