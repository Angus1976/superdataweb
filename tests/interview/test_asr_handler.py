"""Unit tests for ASRWebSocketHandler.

Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.6, 3.7, 5.1, 5.6, 6.1
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.interview.asr_handler import ASRWebSocketHandler
from src.interview.asr_models import CompletionOutline, OutlineTopic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ws() -> AsyncMock:
    """Create a mock WebSocket with common methods."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# Authentication tests
# ---------------------------------------------------------------------------


class TestAuthenticate:
    """Test _authenticate method with various JWT/session scenarios."""

    @pytest.mark.asyncio
    async def test_invalid_jwt_closes_with_4008(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "bad-token")

        mock_security = MagicMock()
        mock_security.get_current_tenant.side_effect = Exception("Invalid token")

        with patch("src.interview.asr_handler._get_security", return_value=mock_security):
            result = await handler._authenticate()

        assert result is None
        ws.close.assert_called_once_with(code=4008, reason="Authentication failed")

    @pytest.mark.asyncio
    async def test_session_not_found_closes_with_4004(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "nonexistent", "token")

        mock_security = MagicMock()
        mock_security.get_current_tenant.return_value = "tenant-1"

        with patch("src.interview.asr_handler._get_security", return_value=mock_security), \
             patch("src.interview.asr_handler._get_sessions", return_value={}):
            result = await handler._authenticate()

        assert result is None
        ws.close.assert_called_once_with(code=4004, reason="Session not found")

    @pytest.mark.asyncio
    async def test_session_wrong_tenant_closes_with_4004(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        mock_security = MagicMock()
        mock_security.get_current_tenant.return_value = "tenant-B"

        sessions = {
            "sess-1": {"tenant_id": "tenant-A", "status": "active"},
        }

        with patch("src.interview.asr_handler._get_security", return_value=mock_security), \
             patch("src.interview.asr_handler._get_sessions", return_value=sessions):
            result = await handler._authenticate()

        assert result is None
        ws.close.assert_called_once_with(code=4004, reason="Session not found")

    @pytest.mark.asyncio
    async def test_completed_session_closes_with_4009(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        mock_security = MagicMock()
        mock_security.get_current_tenant.return_value = "tenant-1"

        sessions = {
            "sess-1": {"tenant_id": "tenant-1", "status": "completed"},
        }

        with patch("src.interview.asr_handler._get_security", return_value=mock_security), \
             patch("src.interview.asr_handler._get_sessions", return_value=sessions):
            result = await handler._authenticate()

        assert result is None
        ws.close.assert_called_once_with(code=4009, reason="Session already ended")

    @pytest.mark.asyncio
    async def test_terminated_session_closes_with_4009(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        mock_security = MagicMock()
        mock_security.get_current_tenant.return_value = "tenant-1"

        sessions = {
            "sess-1": {"tenant_id": "tenant-1", "status": "terminated"},
        }

        with patch("src.interview.asr_handler._get_security", return_value=mock_security), \
             patch("src.interview.asr_handler._get_sessions", return_value=sessions):
            result = await handler._authenticate()

        assert result is None
        ws.close.assert_called_once_with(code=4009, reason="Session already ended")

    @pytest.mark.asyncio
    async def test_valid_auth_returns_tenant_id(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        mock_security = MagicMock()
        mock_security.get_current_tenant.return_value = "tenant-1"

        sessions = {
            "sess-1": {"tenant_id": "tenant-1", "status": "active"},
        }

        with patch("src.interview.asr_handler._get_security", return_value=mock_security), \
             patch("src.interview.asr_handler._get_sessions", return_value=sessions):
            result = await handler._authenticate()

        assert result == "tenant-1"
        ws.close.assert_not_called()


# ---------------------------------------------------------------------------
# Transcript sending tests
# ---------------------------------------------------------------------------


class TestSendTranscript:
    """Test _send_transcript pushes correct JSON."""

    @pytest.mark.asyncio
    async def test_sends_transcript_json(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        await handler._send_transcript("hello world", 0.0, 2.5, is_final=False)

        ws.send_json.assert_called_once_with({
            "type": "transcript",
            "text": "hello world",
            "start_time": 0.0,
            "end_time": 2.5,
            "is_final": False,
        })

    @pytest.mark.asyncio
    async def test_sends_final_transcript(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        await handler._send_transcript("final text", 10.0, 12.5, is_final=True)

        ws.send_json.assert_called_once_with({
            "type": "transcript",
            "text": "final text",
            "start_time": 10.0,
            "end_time": 12.5,
            "is_final": True,
        })


# ---------------------------------------------------------------------------
# Error sending tests
# ---------------------------------------------------------------------------


class TestSendError:
    """Test _send_error pushes correct error JSON without closing."""

    @pytest.mark.asyncio
    async def test_sends_error_json(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        await handler._send_error("transcription_failed", "model error")

        ws.send_json.assert_called_once_with({
            "type": "error",
            "error_code": "transcription_failed",
            "error_message": "model error",
        })
        ws.close.assert_not_called()


# ---------------------------------------------------------------------------
# Outline trigger condition tests
# ---------------------------------------------------------------------------


class TestMaybeGenerateOutline:
    """Test _maybe_generate_outline trigger conditions."""

    @pytest.mark.asyncio
    async def test_no_trigger_below_30s(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")
        handler.total_audio_seconds = 20.0
        handler.last_outline_seconds = 0.0

        await handler._maybe_generate_outline()

        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_trigger_new_below_15s(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")
        handler.total_audio_seconds = 40.0
        handler.last_outline_seconds = 30.0  # only 10s new

        await handler._maybe_generate_outline()

        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_trigger_when_conditions_met(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")
        handler.total_audio_seconds = 45.0
        handler.last_outline_seconds = 0.0
        handler.accumulated_text = "some transcript text"

        mock_cache = AsyncMock()
        mock_cache.load_context = AsyncMock(return_value={})

        mock_session_mgr = MagicMock()
        mock_session_mgr._cache = mock_cache

        mock_outline = CompletionOutline(
            topics=[OutlineTopic(topic_name="Topic 1", description="Desc 1")]
        )
        handler._outline_generator = MagicMock()
        handler._outline_generator.generate = AsyncMock(return_value=mock_outline)

        with patch("src.interview.asr_handler._get_session_mgr", return_value=mock_session_mgr):
            await handler._maybe_generate_outline()

        assert handler.last_outline_seconds == 45.0
        ws.send_json.assert_called_once()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "outline"
        assert len(sent["topics"]) == 1


# ---------------------------------------------------------------------------
# Process audio chunk tests
# ---------------------------------------------------------------------------


class TestProcessAudioChunk:
    """Test _process_audio_chunk buffering and transcription trigger."""

    @pytest.mark.asyncio
    async def test_small_chunk_does_not_trigger_transcription(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        await handler._process_audio_chunk(b"\x00" * 100)

        # No transcription should happen for small chunks
        ws.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_transcription_error_sends_error_frame(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "token")

        # Add enough data to trigger transcription (2.5s at 32kbps = 10000 bytes)
        handler.buffer.add_chunk(b"\x00" * 10000)

        mock_transcriber = AsyncMock()
        mock_transcriber.transcribe = AsyncMock(side_effect=RuntimeError("model crash"))

        with patch("src.interview.asr_handler._get_transcriber", return_value=mock_transcriber):
            assert handler.buffer.is_ready()
            await handler._process_audio_chunk(b"\x00" * 100)

        # Should have sent an error frame
        ws.send_json.assert_called()
        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "error"
        assert sent["error_code"] == "transcription_failed"
        # Connection should NOT be closed
        ws.close.assert_not_called()


# ---------------------------------------------------------------------------
# Init tests
# ---------------------------------------------------------------------------


class TestHandlerInit:
    """Test ASRWebSocketHandler initialization."""

    def test_initial_state(self) -> None:
        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "my-token")

        assert handler.session_id == "sess-1"
        assert handler.token == "my-token"
        assert handler.accumulated_text == ""
        assert handler.total_audio_seconds == 0.0
        assert handler.last_outline_seconds == 0.0
        assert handler._tenant_id == ""
