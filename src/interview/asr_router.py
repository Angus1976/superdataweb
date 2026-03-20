"""ASR WebSocket 路由。

定义 WebSocket 端点用于实时语音 ASR 转录。
"""

from fastapi import APIRouter, WebSocket

from src.interview.asr_handler import ASRWebSocketHandler

asr_router = APIRouter(prefix="/api/interview", tags=["asr"])


@asr_router.websocket("/sessions/{session_id}/asr")
async def asr_websocket(websocket: WebSocket, session_id: str, token: str = ""):
    """WebSocket 端点：实时语音 ASR 转录。

    - 握手阶段通过 query param `token` 进行 JWT 认证
    - 接收二进制帧（Audio_Chunk）
    - 接收文本帧（JSON 控制消息：{"type":"stop"}）
    - 推送 JSON 帧（Partial_Transcript / Completion_Outline / 错误消息）
    """
    handler = ASRWebSocketHandler(websocket, session_id, token)
    await handler.handle()
