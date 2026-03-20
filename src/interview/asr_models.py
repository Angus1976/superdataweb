"""ASR 流式转录相关的 Pydantic 模型。

定义 PartialTranscript、OutlineTopic、CompletionOutline、
ASRWebSocketMessage、ASRControlMessage 模型，用于 WebSocket
消息的序列化与反序列化。
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class PartialTranscript(BaseModel):
    """部分转录结果 — 单个音频片段的转录输出。"""

    text: str
    start_time: float
    end_time: float
    is_final: bool = False


class OutlineTopic(BaseModel):
    """提纲主题项。"""

    topic_name: str
    description: str


class CompletionOutline(BaseModel):
    """补全提纲 — AI 生成的结构化访谈补充建议。"""

    topics: list[OutlineTopic]


class ASRWebSocketMessage(BaseModel):
    """WebSocket 服务端推送消息的统一格式。"""

    type: str  # "transcript" | "outline" | "session_message" | "error"
    text: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    is_final: Optional[bool] = None
    topics: Optional[list[OutlineTopic]] = None
    ai_response: Optional[dict] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class ASRControlMessage(BaseModel):
    """WebSocket 客户端发送的控制消息。"""

    type: str  # "stop"
