"""Unit tests for LLMClient.

Covers: chat_completion, chat_completion_stream, 429 retry logic,
non-2xx error handling, LLMNotConfiguredError propagation, and
build_messages helper.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.interview.llm_client import LLMClient
from src.interview.llm_config_service import LLMConfigService
from src.interview.llm_models import LLMNotConfiguredError, LLMServiceError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FAKE_CONFIG = {
    "provider_name": "openai",
    "api_key": "sk-test-key-123",
    "base_url": "https://api.example.com/v1",
    "model_name": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 2048,
}


@pytest.fixture
def config_service():
    svc = LLMConfigService()
    svc.get_effective_config = AsyncMock(return_value=FAKE_CONFIG)
    return svc


@pytest.fixture
def client(config_service):
    return LLMClient(config_service)


def _ok_response(content: str = "Hello!") -> httpx.Response:
    """Build a fake 200 response with OpenAI-compatible body."""
    body = {
        "choices": [{"message": {"content": content}}],
    }
    return httpx.Response(200, json=body)


def _error_response(status: int, message: str = "error") -> httpx.Response:
    body = {"error": {"message": message}}
    return httpx.Response(status, json=body)


def _rate_limit_response(retry_after: str = "1") -> httpx.Response:
    return httpx.Response(
        429,
        json={"error": {"message": "rate limited"}},
        headers={"Retry-After": retry_after},
    )


# ---------------------------------------------------------------------------
# chat_completion tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completion_success(client):
    """Successful chat completion returns content string."""
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _ok_response("Hi there")
        result = await client.chat_completion("t1", [{"role": "user", "content": "hi"}])
    assert result == "Hi there"


@pytest.mark.asyncio
async def test_chat_completion_uses_config_defaults(client, config_service):
    """When temperature/max_tokens not passed, uses config values."""
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _ok_response("ok")
        await client.chat_completion("t1", [{"role": "user", "content": "hi"}])
        call_kwargs = mock_post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 2048
        assert payload["model"] == "gpt-4"


@pytest.mark.asyncio
async def test_chat_completion_overrides_params(client):
    """Explicit temperature/max_tokens override config values."""
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _ok_response("ok")
        await client.chat_completion(
            "t1", [{"role": "user", "content": "hi"}],
            temperature=0.2, max_tokens=100,
        )
        payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args[1].get("json")
        assert payload["temperature"] == 0.2
        assert payload["max_tokens"] == 100


@pytest.mark.asyncio
async def test_chat_completion_not_configured(config_service):
    """LLMNotConfiguredError propagates when no config."""
    config_service.get_effective_config = AsyncMock(side_effect=LLMNotConfiguredError())
    client = LLMClient(config_service)
    with pytest.raises(LLMNotConfiguredError):
        await client.chat_completion("t1", [{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_completion_non_2xx_raises(client):
    """Non-2xx non-429 response raises LLMServiceError."""
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _error_response(500, "internal error")
        with pytest.raises(LLMServiceError) as exc_info:
            await client.chat_completion("t1", [{"role": "user", "content": "hi"}])
        assert exc_info.value.status_code == 500
        assert "internal error" in exc_info.value.message


@pytest.mark.asyncio
async def test_chat_completion_401_raises(client):
    """401 raises LLMServiceError."""
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _error_response(401, "invalid api key")
        with pytest.raises(LLMServiceError) as exc_info:
            await client.chat_completion("t1", [{"role": "user", "content": "hi"}])
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# 429 retry tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_completion_429_retries_then_succeeds(client):
    """429 followed by 200 succeeds after retry."""
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            _rate_limit_response("0"),
            _ok_response("after retry"),
        ]
        with patch("src.interview.llm_client.asyncio.sleep", new_callable=AsyncMock):
            result = await client.chat_completion("t1", [{"role": "user", "content": "hi"}])
    assert result == "after retry"
    assert mock_post.call_count == 2


@pytest.mark.asyncio
async def test_chat_completion_429_exhausts_retries(client):
    """429 three times in a row raises LLMServiceError after 2 retries."""
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = _rate_limit_response("0")
        with patch("src.interview.llm_client.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMServiceError) as exc_info:
                await client.chat_completion("t1", [{"role": "user", "content": "hi"}])
        assert exc_info.value.status_code == 429
    # 1 initial + 2 retries = 3 calls
    assert mock_post.call_count == 3


@pytest.mark.asyncio
async def test_chat_completion_429_reads_retry_after(client):
    """Retry-After header value is respected."""
    with patch.object(client._http, "post", new_callable=AsyncMock) as mock_post:
        mock_post.side_effect = [
            _rate_limit_response("2"),
            _ok_response("ok"),
        ]
        with patch("src.interview.llm_client.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await client.chat_completion("t1", [{"role": "user", "content": "hi"}])
            mock_sleep.assert_awaited_once_with(2.0)


# ---------------------------------------------------------------------------
# build_messages tests
# ---------------------------------------------------------------------------


def test_build_messages_basic():
    """build_messages produces correct structure."""
    msgs = LLMClient.build_messages(
        system_prompt="You are helpful.",
        history=[
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ],
        user_message="how are you?",
    )
    assert len(msgs) == 4
    assert msgs[0] == {"role": "system", "content": "You are helpful."}
    assert msgs[1] == {"role": "user", "content": "hi"}
    assert msgs[2] == {"role": "assistant", "content": "hello"}
    assert msgs[3] == {"role": "user", "content": "how are you?"}


def test_build_messages_empty_history():
    """build_messages with no history has system + user."""
    msgs = LLMClient.build_messages("sys", [], "msg")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
