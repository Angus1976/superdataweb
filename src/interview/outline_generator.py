"""AI 提纲生成器 — 基于累积转录文本生成访谈补全提纲。

使用 LLMClient 调用 LLM，分析已转录内容并生成结构化的
CompletionOutline，帮助用户发现遗漏话题。异常时返回空提纲，
不影响转录流程。
"""

from __future__ import annotations

import json
import logging

from src.interview.asr_models import CompletionOutline, OutlineTopic
from src.interview.llm_client import LLMClient

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "你是一位专业的访谈分析助手。根据用户提供的访谈转录文本和会话上下文，"
    "分析当前访谈内容，找出可能遗漏或需要补充的话题。\n\n"
    "请以 JSON 格式返回结果，格式如下：\n"
    '{"topics": [{"topic_name": "主题名称", "description": "补充说明"}, ...]}\n\n'
    "要求：\n"
    "1. 每个主题的 topic_name 和 description 都不能为空\n"
    "2. 只返回 JSON，不要包含其他文字\n"
    "3. 如果没有需要补充的话题，返回 {\"topics\": []}"
)


class OutlineGenerator:
    """基于累积转录文本和会话上下文生成访谈补全提纲。"""

    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def generate(
        self,
        accumulated_transcript: str,
        session_context: dict,
    ) -> CompletionOutline:
        """生成补全提纲。

        Args:
            accumulated_transcript: 当前录音会话的累积转录文本
            session_context: 会话上下文（含历史消息、模板等）

        Returns:
            CompletionOutline 包含结构化主题列表。
            异常时返回空提纲 ``CompletionOutline(topics=[])``。
        """
        if self._llm_client is None:
            logger.debug("OutlineGenerator: no LLM client configured, returning empty outline")
            return CompletionOutline(topics=[])

        try:
            user_message = self._build_user_message(accumulated_transcript, session_context)
            messages = LLMClient.build_messages(_SYSTEM_PROMPT, [], user_message)

            tenant_id = session_context.get("tenant_id", "")
            raw_response = await self._llm_client.chat_completion(tenant_id, messages)

            return self._parse_response(raw_response)
        except Exception:
            logger.exception("OutlineGenerator: failed to generate outline, returning empty")
            return CompletionOutline(topics=[])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_message(accumulated_transcript: str, session_context: dict) -> str:
        """Compose the user prompt from transcript and context."""
        parts = [f"以下是当前访谈的转录文本：\n\n{accumulated_transcript}"]

        history = session_context.get("messages")
        if history:
            history_text = "\n".join(
                f"[{m.get('role', '?')}] {m.get('content', '')}"
                for m in history[-10:]  # last 10 messages for context
            )
            parts.append(f"\n\n以下是之前的对话历史（最近 10 条）：\n\n{history_text}")

        template_info = session_context.get("template_name") or session_context.get("industry")
        if template_info:
            parts.append(f"\n\n访谈行业/模板：{template_info}")

        parts.append("\n\n请分析以上内容，生成需要补充的话题提纲。")
        return "".join(parts)

    @staticmethod
    def _parse_response(raw: str) -> CompletionOutline:
        """Parse LLM response text into a CompletionOutline.

        Attempts JSON extraction; falls back to empty outline on failure.
        """
        text = raw.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            # Remove first and last fence lines
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()

        data = json.loads(text)

        topics: list[OutlineTopic] = []
        for item in data.get("topics", []):
            name = (item.get("topic_name") or "").strip()
            desc = (item.get("description") or "").strip()
            if name and desc:
                topics.append(OutlineTopic(topic_name=name, description=desc))

        return CompletionOutline(topics=topics)
