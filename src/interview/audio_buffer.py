"""音频缓冲管理器。

管理音频分片的累积和分段。累积 Audio_Chunk 直到达到目标时长（2-3 秒），
然后返回完整的音频数据供转录。使用 opus 平均码率（~32kbps）估算时长。
"""

from __future__ import annotations

# Opus average bitrate used for duration estimation (bits per second).
_OPUS_AVG_BITRATE_BPS = 32_000


class AudioBufferManager:
    """管理音频分片的累积和分段。

    累积 Audio_Chunk 直到达到目标时长（2-3 秒），
    然后返回完整的音频数据供转录。
    """

    def __init__(self, target_duration_sec: float = 2.5) -> None:
        self.target_duration_sec = target_duration_sec
        self._chunks: list[bytes] = []
        self._total_bytes: int = 0

    def add_chunk(self, data: bytes) -> None:
        """添加一个音频分片到缓冲区。"""
        if data:
            self._chunks.append(data)
            self._total_bytes += len(data)

    def is_ready(self) -> bool:
        """缓冲区是否达到目标时长（基于 opus 码率估算）。"""
        return self.estimate_duration() >= self.target_duration_sec

    def flush(self) -> bytes | None:
        """取出并清空缓冲区，返回合并的音频数据。

        如果缓冲区为空则返回 ``None``。
        """
        if not self._chunks:
            return None
        merged = b"".join(self._chunks)
        self._chunks.clear()
        self._total_bytes = 0
        return merged

    def estimate_duration(self) -> float:
        """基于 opus 平均码率（~32kbps）估算当前缓冲区时长（秒）。

        公式: duration = total_bytes * 8 / bitrate_bps
        """
        if self._total_bytes == 0:
            return 0.0
        return (self._total_bytes * 8) / _OPUS_AVG_BITRATE_BPS
