"""Audio transcription service using faster-whisper (CTranslate2).

Supports multiple audio formats via ffmpeg + pydub conversion.
Converts any input format to WAV before feeding to Whisper.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from dataclasses import dataclass

from pydub import AudioSegment

# Supported audio formats (ffmpeg-backed)
SUPPORTED_AUDIO_FORMATS: set[str] = {
    "mp3", "wav", "flac", "ogg", "m4a", "aac",
    "wma", "opus", "webm", "amr", "mp4", "mpeg",
}


@dataclass
class TranscriptionResult:
    """Result of audio transcription."""
    text: str
    language: str
    duration_seconds: float
    segments: list[dict]


class AudioTranscriber:
    """Transcribes audio files using faster-whisper (CTranslate2).

    Lazily loads the model on first use to avoid slow startup.
    """

    def __init__(self, model_name: str = "base") -> None:
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            self._model = WhisperModel(
                self._model_name, device="cpu", compute_type="int8"
            )
        return self._model

    def _convert_to_wav(self, audio_bytes: bytes, ext: str) -> str:
        """Convert audio bytes to a temporary WAV file."""
        with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp_in:
            tmp_in.write(audio_bytes)
            tmp_in_path = tmp_in.name

        try:
            audio = AudioSegment.from_file(tmp_in_path, format=ext)
            wav_path = tmp_in_path.rsplit(".", 1)[0] + ".wav"
            audio.export(wav_path, format="wav")
            return wav_path
        finally:
            if os.path.exists(tmp_in_path):
                os.unlink(tmp_in_path)

    async def transcribe(
        self, audio_bytes: bytes, ext: str, language: str | None = None
    ) -> TranscriptionResult:
        """Transcribe audio bytes to text.

        Args:
            audio_bytes: Raw audio file content.
            ext: File extension (e.g. "mp3", "wav").
            language: Optional language hint (e.g. "zh", "en").

        Returns:
            TranscriptionResult with text, language, duration, and segments.
        """
        if ext not in SUPPORTED_AUDIO_FORMATS:
            raise ValueError(
                f"Unsupported audio format: .{ext}. "
                f"Supported: {', '.join(sorted(SUPPORTED_AUDIO_FORMATS))}"
            )

        loop = asyncio.get_event_loop()
        wav_path = await loop.run_in_executor(
            None, self._convert_to_wav, audio_bytes, ext
        )

        try:
            model = self._get_model()
            kwargs: dict = {}
            if language:
                kwargs["language"] = language

            # faster-whisper returns (segments_generator, info)
            segments_gen, info = await loop.run_in_executor(
                None, lambda: model.transcribe(wav_path, **kwargs)
            )
            # Materialise segments (generator)
            raw_segments = await loop.run_in_executor(
                None, lambda: list(segments_gen)
            )

            text_parts = []
            segments = []
            for seg in raw_segments:
                text_parts.append(seg.text.strip())
                segments.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })

            # Duration from audio file
            audio = AudioSegment.from_wav(wav_path)
            duration = len(audio) / 1000.0

            return TranscriptionResult(
                text=" ".join(text_parts),
                language=info.language or language or "unknown",
                duration_seconds=round(duration, 2),
                segments=segments,
            )
        finally:
            if os.path.exists(wav_path):
                os.unlink(wav_path)
