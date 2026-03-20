"""LLM 配置管理相关的 Pydantic 模型与异常类。

定义 LLMConfigRequest、LLMConfigResponse、ConnectivityResult、
StructuredPromptRequest、ChatMessage 模型，以及 LLMServiceError
和 LLMNotConfiguredError 异常类。
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 请求 / 响应模型
# ---------------------------------------------------------------------------


class LLMConfigRequest(BaseModel):
    """LLM 配置创建/更新请求。"""

    provider_name: str = Field(..., max_length=50)
    api_key: str = Field(..., min_length=1)
    base_url: str = Field(..., max_length=512)
    model_name: str = Field(..., max_length=100)
    temperature: float = Field(0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(2048, ge=1, le=32000)


class LLMConfigResponse(BaseModel):
    """LLM 配置响应（api_key 掩码显示）。"""

    configured: bool
    provider_name: Optional[str] = None
    api_key_masked: Optional[str] = None
    base_url: Optional[str] = None
    model_name: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


class ConnectivityResult(BaseModel):
    """LLM 连通性测试结果。"""

    ok: bool
    message: str
    model: Optional[str] = None
    response_time_ms: Optional[int] = None


class StructuredPromptRequest(BaseModel):
    """结构化提示词请求（四分区编辑）。"""

    role_definition: str = ""
    task_description: str = ""
    behavior_rules: str = ""
    output_format: str = ""


class ChatMessage(BaseModel):
    """LLM 聊天消息。"""

    role: Literal["system", "user", "assistant"]
    content: str


# ---------------------------------------------------------------------------
# 异常类
# ---------------------------------------------------------------------------


class LLMServiceError(Exception):
    """LLM 服务调用错误，包含 status_code 和 message。"""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"LLM 服务错误 [{status_code}]: {message}")


class LLMNotConfiguredError(Exception):
    """LLM 服务未配置。"""

    def __init__(self, message: str = "LLM 服务未配置，请联系管理员") -> None:
        self.message = message
        super().__init__(message)
