"""Unit tests for AudioBufferManager.

Validates: Requirements 3.3, 3.7
"""

from __future__ import annotations

from src.interview.audio_buffer import AudioBufferManager, _OPUS_AVG_BITRATE_BPS


class TestAudioBufferManagerInit:
    """Verify default and custom initialisation."""

    def test_default_target_duration(self) -> None:
        buf = AudioBufferManager()
        assert buf.target_duration_sec == 2.5

    def test_custom_target_duration(self) -> None:
        buf = AudioBufferManager(target_duration_sec=3.0)
        assert buf.target_duration_sec == 3.0

    def test_initial_state_empty(self) -> None:
        buf = AudioBufferManager()
        assert buf.estimate_duration() == 0.0
        assert buf.is_ready() is False
        assert buf.flush() is None


class TestAddChunk:
    """Verify add_chunk accumulates data correctly."""

    def test_add_single_chunk(self) -> None:
        buf = AudioBufferManager()
        buf.add_chunk(b"\x00" * 100)
        assert buf._total_bytes == 100

    def test_add_multiple_chunks(self) -> None:
        buf = AudioBufferManager()
        buf.add_chunk(b"\x01" * 50)
        buf.add_chunk(b"\x02" * 75)
        assert buf._total_bytes == 125

    def test_add_empty_chunk_ignored(self) -> None:
        buf = AudioBufferManager()
        buf.add_chunk(b"")
        assert buf._total_bytes == 0
        assert buf.flush() is None


class TestEstimateDuration:
    """Verify opus-based duration estimation."""

    def test_empty_buffer_zero_duration(self) -> None:
        buf = AudioBufferManager()
        assert buf.estimate_duration() == 0.0

    def test_known_byte_count(self) -> None:
        buf = AudioBufferManager()
        # 32kbps = 4000 bytes/sec → 4000 bytes should be ~1 second
        bytes_per_sec = _OPUS_AVG_BITRATE_BPS // 8
        buf.add_chunk(b"\x00" * bytes_per_sec)
        assert abs(buf.estimate_duration() - 1.0) < 1e-9


class TestIsReady:
    """Verify readiness check against target duration."""

    def test_not_ready_below_threshold(self) -> None:
        buf = AudioBufferManager(target_duration_sec=2.5)
        # Add 1 second worth of data
        bytes_per_sec = _OPUS_AVG_BITRATE_BPS // 8
        buf.add_chunk(b"\x00" * bytes_per_sec)
        assert buf.is_ready() is False

    def test_ready_at_threshold(self) -> None:
        buf = AudioBufferManager(target_duration_sec=2.5)
        bytes_per_sec = _OPUS_AVG_BITRATE_BPS // 8
        buf.add_chunk(b"\x00" * int(bytes_per_sec * 2.5))
        assert buf.is_ready() is True

    def test_ready_above_threshold(self) -> None:
        buf = AudioBufferManager(target_duration_sec=2.5)
        bytes_per_sec = _OPUS_AVG_BITRATE_BPS // 8
        buf.add_chunk(b"\x00" * (bytes_per_sec * 3))
        assert buf.is_ready() is True


class TestFlush:
    """Verify flush returns merged data and resets state."""

    def test_flush_empty_returns_none(self) -> None:
        buf = AudioBufferManager()
        assert buf.flush() is None

    def test_flush_returns_concatenated_data(self) -> None:
        buf = AudioBufferManager()
        buf.add_chunk(b"\x01\x02")
        buf.add_chunk(b"\x03\x04")
        result = buf.flush()
        assert result == b"\x01\x02\x03\x04"

    def test_flush_resets_buffer(self) -> None:
        buf = AudioBufferManager()
        buf.add_chunk(b"\x00" * 100)
        buf.flush()
        assert buf._total_bytes == 0
        assert buf.estimate_duration() == 0.0
        assert buf.is_ready() is False
        assert buf.flush() is None

    def test_flush_after_stop_returns_remaining(self) -> None:
        """Requirement 3.7: flush returns remaining data even below threshold."""
        buf = AudioBufferManager(target_duration_sec=2.5)
        buf.add_chunk(b"\xAA" * 10)  # well below threshold
        assert buf.is_ready() is False
        result = buf.flush()
        assert result == b"\xAA" * 10
