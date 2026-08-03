from __future__ import annotations

import asyncio
import tempfile
from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel
from openai import AsyncOpenAI
from telegram import Message

from reports_wagent.config import Settings


@dataclass(frozen=True, slots=True)
class AudioPayload:
    filename: str
    content: bytes


class TranscriptionService:
    def __init__(self, settings: Settings) -> None:
        self._provider = settings.transcription_provider
        self._language = settings.transcription_language
        self._openai_client: AsyncOpenAI | None = None
        self._openai_model = settings.transcription_model
        self._local_model: WhisperModel | None = None
        self._local_model_name = settings.local_transcription_model
        self._local_device = settings.local_transcription_device
        self._local_compute_type = settings.local_transcription_compute_type
        self._local_model_dir = settings.local_transcription_model_dir

        if self._provider == "openai" and settings.openai_api_key is None:
            msg = "OPENAI_API_KEY is required for audio transcription."
            raise ValueError(msg)
        if self._provider == "openai":
            self._openai_client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def transcribe(self, payload: AudioPayload) -> str:
        if self._provider == "openai":
            return await self._transcribe_openai(payload)
        if self._provider == "local":
            return await asyncio.to_thread(self._transcribe_local, payload)
        msg = "Audio transcription is disabled."
        raise ValueError(msg)

    async def _transcribe_openai(self, payload: AudioPayload) -> str:
        kwargs = {}
        if self._language is not None:
            kwargs["language"] = self._language
        if self._openai_client is None:
            msg = "OpenAI transcription client is not configured."
            raise ValueError(msg)
        result = await self._openai_client.audio.transcriptions.create(
            model=self._openai_model,
            file=(payload.filename, payload.content),
            **kwargs,
        )
        text = getattr(result, "text", result)
        return str(text).strip()

    def _transcribe_local(self, payload: AudioPayload) -> str:
        model = self._get_local_model()
        suffix = Path(payload.filename).suffix or ".ogg"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as audio_file:
            audio_file.write(payload.content)
            audio_path = audio_file.name
        try:
            kwargs = {}
            if self._language is not None:
                kwargs["language"] = self._language
            segments, _info = model.transcribe(audio_path, **kwargs)
            return " ".join(segment.text.strip() for segment in segments).strip()
        finally:
            Path(audio_path).unlink(missing_ok=True)

    def _get_local_model(self) -> WhisperModel:
        if self._local_model is None:
            download_root = (
                str(self._local_model_dir)
                if self._local_model_dir is not None
                else None
            )
            self._local_model = WhisperModel(
                self._local_model_name,
                device=self._local_device,
                compute_type=self._local_compute_type,
                download_root=download_root,
            )
        return self._local_model


async def audio_payload_from_message(message: Message) -> AudioPayload | None:
    voice = message.voice
    if voice is not None:
        tg_file = await voice.get_file()
        content = bytes(await tg_file.download_as_bytearray())
        return AudioPayload(filename="telegram_voice.ogg", content=content)

    audio = message.audio
    if audio is None:
        return None

    tg_file = await audio.get_file()
    content = bytes(await tg_file.download_as_bytearray())
    filename = audio.file_name or "telegram_audio.mp3"
    return AudioPayload(filename=filename, content=content)
