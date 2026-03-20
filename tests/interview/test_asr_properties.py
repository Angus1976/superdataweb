"""Property-based tests for ASR models and WebSocket messages.

**Validates: Requirements 3.3, 3.4, 3.7**
"""

from __future__ import annotations

import json

from hypothesis import given, settings as h_settings, strategies as st

from src.interview.asr_models import (
    ASRWebSocketMessage,
    CompletionOutline,
    OutlineTopic,
    PartialTranscript,
)
from src.interview.audio_buffer import AudioBufferManager, _OPUS_AVG_BITRATE_BPS


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Generate valid PartialTranscript instances with non-empty text and valid times
_partial_transcript_strategy = st.builds(
    PartialTranscript,
    text=st.text(min_size=1, max_size=500).filter(lambda t: t.strip()),
    start_time=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    end_time=st.nothing(),  # placeholder, overridden below
    is_final=st.booleans(),
)


def _valid_partial_transcript():
    """Strategy that ensures end_time > start_time and start_time >= 0."""
    return (
        st.tuples(
            st.text(min_size=1, max_size=500).filter(lambda t: t.strip()),
            st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
            st.floats(min_value=0.01, max_value=1e4, allow_nan=False, allow_infinity=False),
            st.booleans(),
        )
        .map(lambda args: PartialTranscript(
            text=args[0],
            start_time=args[1],
            end_time=args[1] + args[2],  # guarantees end_time > start_time
            is_final=args[3],
        ))
    )


# ---------------------------------------------------------------------------
# Strategy – Audio chunks for AudioBufferManager
# ---------------------------------------------------------------------------

# Bytes per second at opus ~32kbps
_BYTES_PER_SEC = _OPUS_AVG_BITRATE_BPS // 8  # 4000


def _audio_chunks_reaching_threshold(target_sec: float = 2.5):
    """Strategy that generates a list of non-empty byte chunks whose total
    size is guaranteed to reach the target duration threshold.

    Each chunk is between 1 and 2000 bytes.  Extra chunks are appended so
    the total always meets or exceeds the threshold.
    """
    min_bytes = int(target_sec * _BYTES_PER_SEC)

    return (
        st.lists(
            st.binary(min_size=1, max_size=2000),
            min_size=1,
            max_size=50,
        )
        .map(lambda chunks: _ensure_threshold(chunks, min_bytes))
    )


def _ensure_threshold(chunks: list[bytes], min_bytes: int) -> list[bytes]:
    """Append a padding chunk if the total size is below *min_bytes*."""
    total = sum(len(c) for c in chunks)
    if total < min_bytes:
        chunks = list(chunks) + [b"\x00" * (min_bytes - total)]
    return chunks


# ---------------------------------------------------------------------------
# Property 5: 音频缓冲区累积与刷新
# ---------------------------------------------------------------------------


class TestAudioBufferAccumulationAndFlush:
    """# Feature: realtime-voice-asr, Property 5: 音频缓冲区累积与刷新

    For any sequence of audio chunks, AudioBufferManager should report
    `is_ready() == True` once the estimated duration reaches the target
    threshold; `flush()` must return the concatenation of all added chunks;
    and after flushing the buffer must be empty.

    **Validates: Requirements 3.3, 3.7**
    """

    @given(chunks=_audio_chunks_reaching_threshold())
    @h_settings(max_examples=100, deadline=None)
    def test_property_5_is_ready_when_threshold_reached(
        self, chunks: list[bytes]
    ) -> None:
        """# Feature: realtime-voice-asr, Property 5: 音频缓冲区累积与刷新

        When accumulated data reaches the target duration threshold,
        is_ready() must return True."""
        buf = AudioBufferManager(target_duration_sec=2.5)
        for chunk in chunks:
            buf.add_chunk(chunk)

        assert buf.is_ready() is True, (
            f"Expected is_ready() == True after adding "
            f"{sum(len(c) for c in chunks)} bytes "
            f"(estimated {buf.estimate_duration():.2f}s)"
        )

    @given(chunks=st.lists(st.binary(min_size=1, max_size=2000), min_size=1, max_size=50))
    @h_settings(max_examples=100, deadline=None)
    def test_property_5_flush_returns_concatenation(
        self, chunks: list[bytes]
    ) -> None:
        """# Feature: realtime-voice-asr, Property 5: 音频缓冲区累积与刷新

        flush() must return the byte-wise concatenation of all added chunks."""
        buf = AudioBufferManager()
        for chunk in chunks:
            buf.add_chunk(chunk)

        expected = b"".join(chunks)
        result = buf.flush()

        assert result == expected, "flush() did not return concatenation of all chunks"

    @given(chunks=st.lists(st.binary(min_size=1, max_size=2000), min_size=1, max_size=50))
    @h_settings(max_examples=100, deadline=None)
    def test_property_5_buffer_empty_after_flush(
        self, chunks: list[bytes]
    ) -> None:
        """# Feature: realtime-voice-asr, Property 5: 音频缓冲区累积与刷新

        After flush(), the buffer must be empty: is_ready() == False,
        estimate_duration() == 0, and a second flush() returns None."""
        buf = AudioBufferManager()
        for chunk in chunks:
            buf.add_chunk(chunk)

        buf.flush()

        assert buf.is_ready() is False, "Buffer should not be ready after flush"
        assert buf.estimate_duration() == 0.0, "Duration should be 0 after flush"
        assert buf.flush() is None, "Second flush should return None"


# ---------------------------------------------------------------------------
# Property 6: 转录结果 JSON 格式完整性
# ---------------------------------------------------------------------------


class TestTranscriptJsonFormatCompleteness:
    """# Feature: realtime-voice-asr, Property 6: 转录结果 JSON 格式完整性

    For any valid PartialTranscript, the ASRWebSocketMessage serialized as JSON
    must contain type="transcript", non-empty text, start_time >= 0, and
    end_time > start_time.

    **Validates: Requirements 3.4**
    """

    @given(transcript=_valid_partial_transcript())
    @h_settings(max_examples=100, deadline=None)
    def test_property_6_transcript_json_completeness(self, transcript: PartialTranscript) -> None:
        """# Feature: realtime-voice-asr, Property 6: 转录结果 JSON 格式完整性

        ASRWebSocketMessage built from a PartialTranscript must serialize to
        JSON with all required fields and correct constraints."""
        msg = ASRWebSocketMessage(
            type="transcript",
            text=transcript.text,
            start_time=transcript.start_time,
            end_time=transcript.end_time,
            is_final=transcript.is_final,
        )

        data = json.loads(msg.model_dump_json())

        # type must be "transcript"
        assert data["type"] == "transcript"

        # text must be non-empty
        assert isinstance(data["text"], str)
        assert len(data["text"]) > 0

        # start_time >= 0
        assert data["start_time"] >= 0

        # end_time > start_time
        assert data["end_time"] > data["start_time"]


# ---------------------------------------------------------------------------
# Strategies – OutlineTopic / CompletionOutline
# ---------------------------------------------------------------------------

_outline_topic_strategy = st.builds(
    OutlineTopic,
    topic_name=st.text(min_size=1, max_size=200).filter(lambda t: t.strip()),
    description=st.text(min_size=1, max_size=500).filter(lambda t: t.strip()),
)


# ---------------------------------------------------------------------------
# Property 11: 提纲结构完整性 (Outline structure completeness)
# ---------------------------------------------------------------------------


class TestOutlineStructureCompleteness:
    """# Feature: realtime-voice-asr, Property 11: 提纲结构完整性

    For any CompletionOutline built from a non-empty list of OutlineTopic
    instances, every topic must have a non-empty `topic_name` and a non-empty
    `description`.

    **Validates: Requirements 5.3**
    """

    @given(topics=st.lists(_outline_topic_strategy, min_size=1, max_size=20))
    @h_settings(max_examples=100, deadline=None)
    def test_property_11_outline_structure_completeness(
        self, topics: list[OutlineTopic]
    ) -> None:
        """# Feature: realtime-voice-asr, Property 11: 提纲结构完整性

        Every topic in a CompletionOutline must have non-empty topic_name and
        description."""
        outline = CompletionOutline(topics=topics)

        assert len(outline.topics) > 0, "Outline must contain at least one topic"

        for topic in outline.topics:
            assert isinstance(topic.topic_name, str)
            assert len(topic.topic_name) > 0, "topic_name must be non-empty"
            assert topic.topic_name.strip(), "topic_name must not be only whitespace"

            assert isinstance(topic.description, str)
            assert len(topic.description) > 0, "description must be non-empty"
            assert topic.description.strip(), "description must not be only whitespace"


# ---------------------------------------------------------------------------
# Property 10: AI 提纲触发条件
# ---------------------------------------------------------------------------


def should_trigger_outline(
    total_audio_seconds: float,
    seconds_since_last_outline: float,
) -> bool:
    """Determine whether outline generation should be triggered.

    The outline is triggered ONLY when both conditions are met:
    1. Total accumulated audio duration >= 30 seconds
    2. New content since last outline trigger >= 15 seconds

    **Validates: Requirements 5.1, 5.6**
    """
    return total_audio_seconds >= 30.0 and seconds_since_last_outline >= 15.0


class TestOutlineTriggerCondition:
    """# Feature: realtime-voice-asr, Property 10: AI 提纲触发条件

    For any (total_audio_seconds, seconds_since_last_outline) pair, outline
    generation is triggered ONLY when total_audio_seconds >= 30 AND
    seconds_since_last_outline >= 15.

    **Validates: Requirements 5.1, 5.6**
    """

    @given(
        total=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
        new=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    @h_settings(max_examples=200, deadline=None)
    def test_property_10_trigger_iff_both_conditions_met(
        self, total: float, new: float
    ) -> None:
        """# Feature: realtime-voice-asr, Property 10: AI 提纲触发条件

        should_trigger_outline returns True if and only if
        total_audio_seconds >= 30 AND seconds_since_last_outline >= 15."""
        result = should_trigger_outline(total, new)
        expected = total >= 30.0 and new >= 15.0
        assert result == expected, (
            f"should_trigger_outline({total}, {new}) = {result}, expected {expected}"
        )

    @given(
        total=st.floats(min_value=0.0, max_value=29.999, allow_nan=False, allow_infinity=False),
        new=st.floats(min_value=0.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    @h_settings(max_examples=100, deadline=None)
    def test_property_10_no_trigger_when_total_below_30(
        self, total: float, new: float
    ) -> None:
        """# Feature: realtime-voice-asr, Property 10: AI 提纲触发条件

        Outline must NOT trigger when total audio < 30 seconds,
        regardless of new content duration."""
        assert should_trigger_outline(total, new) is False

    @given(
        total=st.floats(min_value=30.0, max_value=1e6, allow_nan=False, allow_infinity=False),
        new=st.floats(min_value=0.0, max_value=14.999, allow_nan=False, allow_infinity=False),
    )
    @h_settings(max_examples=100, deadline=None)
    def test_property_10_no_trigger_when_new_below_15(
        self, total: float, new: float
    ) -> None:
        """# Feature: realtime-voice-asr, Property 10: AI 提纲触发条件

        Outline must NOT trigger when new content < 15 seconds,
        even if total audio >= 30 seconds."""
        assert should_trigger_outline(total, new) is False

    @given(
        total=st.floats(min_value=30.0, max_value=1e6, allow_nan=False, allow_infinity=False),
        new=st.floats(min_value=15.0, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    @h_settings(max_examples=100, deadline=None)
    def test_property_10_trigger_when_both_conditions_met(
        self, total: float, new: float
    ) -> None:
        """# Feature: realtime-voice-asr, Property 10: AI 提纲触发条件

        Outline MUST trigger when total >= 30s AND new >= 15s."""
        assert should_trigger_outline(total, new) is True


# ---------------------------------------------------------------------------
# Property 4: JWT 认证拒绝无效 Token
# ---------------------------------------------------------------------------

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


def _make_ws() -> AsyncMock:
    """Create a mock WebSocket with common methods."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.close = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive = AsyncMock()
    return ws


class TestJWTAuthRejectsInvalidToken:
    """# Feature: realtime-voice-asr, Property 4: JWT 认证拒绝无效 Token

    For any random string token, when the security layer raises an exception
    (indicating the token is invalid), _authenticate must return None and
    close the WebSocket with code 4008.

    **Validates: Requirements 3.2**
    """

    @given(token=st.text(min_size=0, max_size=500))
    @h_settings(max_examples=100, deadline=None)
    def test_property_4_invalid_token_rejected_with_4008(self, token: str) -> None:
        """# Feature: realtime-voice-asr, Property 4: JWT 认证拒绝无效 Token

        Any random string token must be rejected: _authenticate returns None
        and the WebSocket is closed with code 4008."""
        from src.interview.asr_handler import ASRWebSocketHandler

        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", token)

        mock_security = MagicMock()
        mock_security.get_current_tenant.side_effect = Exception("Invalid token")

        with patch("src.interview.asr_handler._get_security", return_value=mock_security):
            result = asyncio.get_event_loop().run_until_complete(handler._authenticate())

        assert result is None, (
            f"Expected _authenticate to return None for token={token!r}, got {result!r}"
        )
        ws.close.assert_called_once_with(code=4008, reason="Authentication failed")


# ---------------------------------------------------------------------------
# Property 7: 转录错误不中断连接
# ---------------------------------------------------------------------------


class TestTranscriptionErrorDoesNotBreakConnection:
    """# Feature: realtime-voice-asr, Property 7: 转录错误不中断连接

    For any random error_code and error_message strings, calling _send_error
    must send a JSON payload with type="error", non-empty error_code and
    error_message, and must NOT close the WebSocket connection.

    **Validates: Requirement 3.6**
    """

    @given(
        error_code=st.text(min_size=1, max_size=200).filter(lambda t: t.strip()),
        error_message=st.text(min_size=1, max_size=500).filter(lambda t: t.strip()),
    )
    @h_settings(max_examples=100, deadline=None)
    def test_property_7_error_does_not_close_connection(
        self, error_code: str, error_message: str
    ) -> None:
        """# Feature: realtime-voice-asr, Property 7: 转录错误不中断连接

        _send_error must send JSON with type="error", non-empty error_code
        and error_message, and must NOT call websocket.close()."""
        from src.interview.asr_handler import ASRWebSocketHandler

        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "tok")

        asyncio.get_event_loop().run_until_complete(
            handler._send_error(error_code, error_message)
        )

        # Verify send_json was called exactly once
        ws.send_json.assert_called_once()
        payload = ws.send_json.call_args[0][0]

        # 1. type must be "error"
        assert payload["type"] == "error", (
            f"Expected type='error', got {payload.get('type')!r}"
        )

        # 2. error_code must be non-empty
        assert "error_code" in payload, "Payload missing 'error_code' field"
        assert isinstance(payload["error_code"], str), "error_code must be a string"
        assert len(payload["error_code"]) > 0, "error_code must be non-empty"

        # 3. error_message must be non-empty
        assert "error_message" in payload, "Payload missing 'error_message' field"
        assert isinstance(payload["error_message"], str), "error_message must be a string"
        assert len(payload["error_message"]) > 0, "error_message must be non-empty"

        # 4. WebSocket close must NOT be called (connection stays open)
        ws.close.assert_not_called()


# ---------------------------------------------------------------------------
# Property 9: 录音结束提交累积文本
# ---------------------------------------------------------------------------


class TestRecordingStopSubmitsAccumulatedText:
    """# Feature: realtime-voice-asr, Property 9: 录音结束提交累积文本

    For any non-empty accumulated transcript, when recording stops,
    the text must be submitted via SessionManager.send_message and the
    message metadata must contain source: "voice".

    **Validates: Requirements 4.4, 6.1, 6.4**
    """

    @given(
        texts=st.lists(
            st.text(min_size=1, max_size=200).filter(lambda t: t.strip()),
            min_size=1,
            max_size=10,
        ),
    )
    @h_settings(max_examples=100, deadline=None)
    def test_property_9_flush_submits_accumulated_text_with_voice_metadata(
        self, texts: list[str]
    ) -> None:
        """# Feature: realtime-voice-asr, Property 9: 录音结束提交累积文本

        When _flush_and_close is called with non-empty accumulated_text,
        send_message must be called with that text and metadata containing
        source: "voice"."""
        from src.interview.asr_handler import ASRWebSocketHandler

        ws = _make_ws()
        handler = ASRWebSocketHandler(ws, "sess-1", "tok")
        handler._tenant_id = "tenant-1"

        # Build accumulated text from the generated text list
        accumulated = " ".join(texts)
        handler.accumulated_text = accumulated + " "

        # Mock session_mgr with an async send_message
        mock_session_mgr = MagicMock()
        mock_ai_response = MagicMock()
        mock_ai_response.model_dump.return_value = {"message": "ok"}
        mock_session_mgr.send_message = AsyncMock(return_value=mock_ai_response)

        # Mock transcriber (buffer is empty, so no transcription needed)
        mock_transcriber = MagicMock()

        with patch("src.interview.asr_handler._get_session_mgr", return_value=mock_session_mgr), \
             patch("src.interview.asr_handler._get_transcriber", return_value=mock_transcriber):
            asyncio.get_event_loop().run_until_complete(handler._flush_and_close())

        # Verify send_message was called
        mock_session_mgr.send_message.assert_called_once()

        call_args = mock_session_mgr.send_message.call_args

        # Verify the text matches accumulated text (stripped)
        submitted_text = call_args[0][2] if len(call_args[0]) > 2 else call_args.kwargs.get("message", "")
        assert submitted_text == accumulated.strip(), (
            f"Expected submitted text to be {accumulated.strip()!r}, got {submitted_text!r}"
        )

        # Verify metadata contains source: "voice"
        submitted_metadata = call_args.kwargs.get("metadata", None)
        assert submitted_metadata is not None, "metadata kwarg must be passed to send_message"
        assert submitted_metadata.get("source") == "voice", (
            f"Expected metadata source='voice', got {submitted_metadata!r}"
        )
