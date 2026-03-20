"""ASR WebSocket 会话处理器。

管理单个 WebSocket ASR 会话的完整生命周期：
JWT 认证 → 接收音频分片 → 缓冲累积 → 转录 → 推送结果 → AI 提纲 → 关闭。

复用 router.py 中的 _security、_session_mgr、_transcriber 单例。
"""

from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect

from src.interview.audio_buffer import AudioBufferManager
from src.interview.asr_models import ASRControlMessage
from src.interview.outline_generator import OutlineGenerator

logger = logging.getLogger(__name__)

# Outline trigger thresholds (seconds)
_OUTLINE_MIN_TOTAL_SECONDS = 30.0
_OUTLINE_MIN_NEW_SECONDS = 15.0


def _get_security():
    """Lazy import of the shared InterviewSecurity singleton."""
    from src.interview.router import _security
    return _security


def _get_session_mgr():
    """Lazy import of the shared SessionManager singleton."""
    from src.interview.router import _session_mgr
    return _session_mgr


def _get_transcriber():
    """Lazy import of the shared AudioTranscriber singleton."""
    from src.interview.router import _transcriber
    return _transcriber


def _get_sessions():
    """Lazy import of the in-memory sessions dict."""
    from src.interview.system import _sessions
    return _sessions


class ASRWebSocketHandler:
    """管理单个 WebSocket ASR 会话的完整生命周期。"""

    def __init__(self, websocket: WebSocket, session_id: str, token: str) -> None:
        self.websocket = websocket
        self.session_id = session_id
        self.token = token

        self.buffer = AudioBufferManager()
        self.accumulated_text: str = ""
        self.total_audio_seconds: float = 0.0
        self.last_outline_seconds: float = 0.0  # audio seconds at last outline trigger

        self._outline_generator = OutlineGenerator()
        self._tenant_id: str = ""

    async def handle(self) -> None:
        """主循环：认证 → 接收音频/控制消息 → 转录 → 推送结果。"""
        await self.websocket.accept()

        tenant_id = await self._authenticate()
        if tenant_id is None:
            return
        self._tenant_id = tenant_id

        try:
            while True:
                message = await self.websocket.receive()

                if message.get("type") == "websocket.disconnect":
                    break

                if "bytes" in message and message["bytes"]:
                    await self._process_audio_chunk(message["bytes"])
                elif "text" in message and message["text"]:
                    try:
                        ctrl = ASRControlMessage.model_validate_json(message["text"])
                        if ctrl.type == "stop":
                            await self._flush_and_close()
                            return
                    except Exception:
                        pass  # ignore malformed control messages

        except WebSocketDisconnect:
            logger.info("ASR WebSocket disconnected: session=%s", self.session_id)
        except Exception:
            logger.exception("ASR WebSocket unexpected error: session=%s", self.session_id)
        finally:
            try:
                await self.websocket.close(code=1000)
            except Exception:
                pass

    async def _authenticate(self) -> str | None:
        """验证 JWT token，返回 tenant_id。失败则关闭连接并返回 None。"""
        security = _get_security()

        # 1. Verify JWT
        try:
            tenant_id = security.get_current_tenant(self.token)
        except Exception:
            await self.websocket.close(code=4008, reason="Authentication failed")
            return None

        # 2. Verify session exists
        sessions = _get_sessions()
        session = sessions.get(self.session_id)
        if session is None:
            await self.websocket.close(code=4004, reason="Session not found")
            return None

        # 3. Verify session belongs to tenant
        if session.get("tenant_id") != tenant_id:
            await self.websocket.close(code=4004, reason="Session not found")
            return None

        # 4. Verify session is still active
        session_status = session.get("status", "")
        if session_status in ("completed", "terminated"):
            await self.websocket.close(code=4009, reason="Session already ended")
            return None

        return tenant_id

    async def _process_audio_chunk(self, data: bytes) -> None:
        """将音频分片加入缓冲区，缓冲区满时触发转录。"""
        self.buffer.add_chunk(data)

        if self.buffer.is_ready():
            await self._transcribe_buffer()

    async def _transcribe_buffer(self) -> str | None:
        """调用 AudioTranscriber 转录缓冲区音频，返回文本。"""
        transcriber = _get_transcriber()

        audio_data = self.buffer.flush()
        if audio_data is None:
            return None

        # Estimate duration of this chunk from the raw bytes
        chunk_duration = (len(audio_data) * 8) / 32_000  # opus ~32kbps

        start_time = self.total_audio_seconds
        end_time = start_time + chunk_duration

        try:
            result = await transcriber.transcribe(audio_data, ext="webm", language="zh")
            text = result.text.strip()
        except Exception as exc:
            logger.exception("Transcription failed: session=%s", self.session_id)
            await self._send_error("transcription_failed", str(exc))
            self.total_audio_seconds = end_time
            return None

        self.total_audio_seconds = end_time

        if text:
            await self._send_transcript(text, start_time, end_time, is_final=False)
            self.accumulated_text += text + " "
            await self._maybe_generate_outline()

        return text

    async def _send_transcript(
        self,
        text: str,
        start_time: float,
        end_time: float,
        is_final: bool = False,
    ) -> None:
        """推送 Partial_Transcript JSON 帧。"""
        payload = {
            "type": "transcript",
            "text": text,
            "start_time": round(start_time, 2),
            "end_time": round(end_time, 2),
            "is_final": is_final,
        }
        await self.websocket.send_json(payload)

    async def _send_error(self, error_code: str, error_message: str) -> None:
        """推送错误 JSON 帧，不中断连接。"""
        payload = {
            "type": "error",
            "error_code": error_code,
            "error_message": error_message,
        }
        await self.websocket.send_json(payload)

    async def _maybe_generate_outline(self) -> None:
        """检查是否需要触发 AI 提纲生成（总时长 ≥ 30s 且新增 ≥ 15s）。"""
        if self.total_audio_seconds < _OUTLINE_MIN_TOTAL_SECONDS:
            return

        new_seconds = self.total_audio_seconds - self.last_outline_seconds
        if new_seconds < _OUTLINE_MIN_NEW_SECONDS:
            return

        try:
            session_mgr = _get_session_mgr()
            context = await session_mgr._cache.load_context(self.session_id) or {}
            outline = await self._outline_generator.generate(
                self.accumulated_text.strip(), context
            )

            self.last_outline_seconds = self.total_audio_seconds

            if outline.topics:
                payload = {
                    "type": "outline",
                    "topics": [t.model_dump() for t in outline.topics],
                }
                await self.websocket.send_json(payload)
        except Exception:
            logger.exception(
                "Outline generation failed: session=%s", self.session_id
            )
            # Silently skip — don't affect transcription flow

    async def _flush_and_close(self) -> None:
        """转录剩余缓冲区，提交累积文本至会话，关闭连接。"""
        session_mgr = _get_session_mgr()

        # Transcribe remaining buffer
        audio_data = self.buffer.flush()
        if audio_data is not None:
            chunk_duration = (len(audio_data) * 8) / 32_000
            start_time = self.total_audio_seconds
            end_time = start_time + chunk_duration

            try:
                transcriber = _get_transcriber()
                result = await transcriber.transcribe(
                    audio_data, ext="webm", language="zh"
                )
                text = result.text.strip()
                if text:
                    self.total_audio_seconds = end_time
                    self.accumulated_text += text + " "
                    await self._send_transcript(text, start_time, end_time, is_final=True)
            except Exception as exc:
                logger.exception(
                    "Final transcription failed: session=%s", self.session_id
                )
                await self._send_error("transcription_failed", str(exc))

        # Submit accumulated text as a user message
        final_text = self.accumulated_text.strip()
        if final_text:
            try:
                ai_response = await session_mgr.send_message(
                    self.session_id, self._tenant_id, final_text,
                    metadata={"source": "voice"},
                )
                # Push AI response to client
                payload = {
                    "type": "session_message",
                    "ai_response": ai_response.model_dump(),
                }
                await self.websocket.send_json(payload)
            except Exception:
                logger.exception(
                    "Failed to submit accumulated text: session=%s",
                    self.session_id,
                )

        # Close connection normally
        await self.websocket.close(code=1000)
