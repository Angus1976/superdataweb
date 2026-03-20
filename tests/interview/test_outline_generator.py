"""Unit tests for OutlineGenerator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.interview.asr_models import CompletionOutline, OutlineTopic
from src.interview.outline_generator import OutlineGenerator


@pytest.mark.asyncio
async def test_generate_returns_empty_when_no_llm_client():
    """No LLM client configured → empty outline."""
    gen = OutlineGenerator(llm_client=None)
    result = await gen.generate("some transcript", {"tenant_id": "t1"})
    assert result == CompletionOutline(topics=[])


@pytest.mark.asyncio
async def test_generate_parses_valid_llm_response():
    """LLM returns valid JSON → parsed into CompletionOutline."""
    llm = MagicMock()
    llm.chat_completion = AsyncMock(return_value=json.dumps({
        "topics": [
            {"topic_name": "预算", "description": "需要补充预算相关信息"},
            {"topic_name": "时间线", "description": "项目时间线尚未明确"},
        ]
    }))

    gen = OutlineGenerator(llm_client=llm)
    result = await gen.generate("我们讨论了项目范围", {"tenant_id": "t1"})

    assert len(result.topics) == 2
    assert result.topics[0].topic_name == "预算"
    assert result.topics[1].topic_name == "时间线"


@pytest.mark.asyncio
async def test_generate_returns_empty_on_llm_exception():
    """LLM raises exception → empty outline, no propagation."""
    llm = MagicMock()
    llm.chat_completion = AsyncMock(side_effect=RuntimeError("LLM down"))

    gen = OutlineGenerator(llm_client=llm)
    result = await gen.generate("transcript", {"tenant_id": "t1"})

    assert result == CompletionOutline(topics=[])


@pytest.mark.asyncio
async def test_generate_returns_empty_on_invalid_json():
    """LLM returns non-JSON → empty outline."""
    llm = MagicMock()
    llm.chat_completion = AsyncMock(return_value="This is not JSON at all")

    gen = OutlineGenerator(llm_client=llm)
    result = await gen.generate("transcript", {"tenant_id": "t1"})

    assert result == CompletionOutline(topics=[])


@pytest.mark.asyncio
async def test_generate_strips_markdown_fences():
    """LLM wraps JSON in markdown code fences → still parsed."""
    raw = '```json\n{"topics": [{"topic_name": "A", "description": "B"}]}\n```'
    llm = MagicMock()
    llm.chat_completion = AsyncMock(return_value=raw)

    gen = OutlineGenerator(llm_client=llm)
    result = await gen.generate("transcript", {"tenant_id": "t1"})

    assert len(result.topics) == 1
    assert result.topics[0].topic_name == "A"


@pytest.mark.asyncio
async def test_generate_filters_empty_topic_fields():
    """Topics with empty name or description are filtered out."""
    llm = MagicMock()
    llm.chat_completion = AsyncMock(return_value=json.dumps({
        "topics": [
            {"topic_name": "Valid", "description": "OK"},
            {"topic_name": "", "description": "missing name"},
            {"topic_name": "No desc", "description": ""},
        ]
    }))

    gen = OutlineGenerator(llm_client=llm)
    result = await gen.generate("transcript", {"tenant_id": "t1"})

    assert len(result.topics) == 1
    assert result.topics[0].topic_name == "Valid"


@pytest.mark.asyncio
async def test_generate_passes_tenant_id_to_llm():
    """tenant_id from session_context is forwarded to chat_completion."""
    llm = MagicMock()
    llm.chat_completion = AsyncMock(return_value='{"topics": []}')

    gen = OutlineGenerator(llm_client=llm)
    await gen.generate("text", {"tenant_id": "my-tenant"})

    llm.chat_completion.assert_called_once()
    call_args = llm.chat_completion.call_args
    assert call_args[0][0] == "my-tenant"


@pytest.mark.asyncio
async def test_generate_includes_history_in_prompt():
    """Session context messages are included in the user prompt."""
    llm = MagicMock()
    llm.chat_completion = AsyncMock(return_value='{"topics": []}')

    ctx = {
        "tenant_id": "t1",
        "messages": [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ],
    }
    gen = OutlineGenerator(llm_client=llm)
    await gen.generate("transcript text", ctx)

    # The user message sent to LLM should contain the history
    call_args = llm.chat_completion.call_args
    messages = call_args[0][1]
    user_msg = messages[-1]["content"]
    assert "hello" in user_msg
    assert "hi there" in user_msg
