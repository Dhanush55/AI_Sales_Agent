"""Voice service with pluggable STT and TTS providers."""
from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
import os
import io
import logging

logger = logging.getLogger(__name__)


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: BinaryIO, language: Optional[str] = None) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, language: str, voice_id: Optional[str] = None) -> bytes: ...

    @property
    @abstractmethod
    def name(self) -> str: ...


LANG_MAP = {
    "indian_english": "en",
    "hindi": "hi",
    "kannada": "kn",
    "tamil": "ta",
}


class OpenAIWhisperSTT(STTProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "openai_whisper"

    async def transcribe(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)
        whisper_lang = LANG_MAP.get(language, "en") if language else None
        transcription = await client.audio.transcriptions.create(
            model="whisper-1", file=audio_data, language=whisper_lang
        )
        return transcription.text


class FasterWhisperSTT(STTProvider):
    """Local, free STT using faster-whisper (CTranslate2)."""

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self._model = None

    @property
    def name(self) -> str:
        return "faster_whisper"

    def _get_model(self):
        if self._model is None:
            from faster_whisper import WhisperModel
            logger.info(f"Loading faster-whisper model: {self.model_size}")
            self._model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
        return self._model

    async def transcribe(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        import asyncio
        import tempfile
        whisper_lang = LANG_MAP.get(language, None)
        audio_bytes = audio_data.read()

        def _run():
            model = self._get_model()
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
                tmp.write(audio_bytes)
                tmp.flush()
                segments, _info = model.transcribe(tmp.name, language=whisper_lang, beam_size=1)
                return " ".join(seg.text for seg in segments).strip()

        return await asyncio.to_thread(_run)


class ElevenLabsTTS(TTSProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.default_voice = "21m00Tcm4TlvDq8ikWAM"

    @property
    def name(self) -> str:
        return "elevenlabs"

    async def synthesize(self, text: str, language: str, voice_id: Optional[str] = None) -> bytes:
        from elevenlabs import ElevenLabs, VoiceSettings
        client = ElevenLabs(api_key=self.api_key)
        voice = voice_id or self.default_voice
        audio_generator = client.text_to_speech.convert(
            text=text, voice_id=voice, model_id="eleven_multilingual_v2",
            voice_settings=VoiceSettings(stability=0.7, similarity_boost=0.8, style=0.0, use_speaker_boost=True),
        )
        return b"".join(audio_generator)


class EdgeTTSProvider(TTSProvider):
    """Free local TTS using Microsoft Edge TTS (edge-tts)."""

    VOICE_MAP = {
        "indian_english": "en-IN-NeerjaNeural",
        "hindi": "hi-IN-SwaraNeural",
        "kannada": "kn-IN-SapnaNeural",
        "tamil": "ta-IN-PallaviNeural",
    }

    @property
    def name(self) -> str:
        return "edge_tts"

    async def synthesize(self, text: str, language: str, voice_id: Optional[str] = None) -> bytes:
        import edge_tts
        voice = voice_id or self.VOICE_MAP.get(language, self.VOICE_MAP["indian_english"])
        communicate = edge_tts.Communicate(text, voice)
        buf = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio":
                buf.write(chunk["data"])
        return buf.getvalue()


class VoiceService:
    def __init__(self):
        self.stt_provider: Optional[STTProvider] = None
        self.tts_provider: Optional[TTSProvider] = None
        self._initialize_providers()

    def _initialize_providers(self):
        stt_type = os.environ.get("STT_PROVIDER", "faster_whisper").lower()
        tts_type = os.environ.get("TTS_PROVIDER", "edge_tts").lower()

        if stt_type == "faster_whisper":
            model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")
            self.stt_provider = FasterWhisperSTT(model_size)
        elif stt_type == "openai_whisper":
            api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                self.stt_provider = OpenAIWhisperSTT(api_key)

        if tts_type == "edge_tts":
            self.tts_provider = EdgeTTSProvider()
        elif tts_type == "elevenlabs":
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if api_key:
                self.tts_provider = ElevenLabsTTS(api_key)

    async def speech_to_text(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        if not self.stt_provider:
            raise RuntimeError("STT provider not configured.")
        return await self.stt_provider.transcribe(audio_data, language)

    async def text_to_speech(self, text: str, language: str, voice_id: Optional[str] = None) -> bytes:
        if not self.tts_provider:
            raise RuntimeError("TTS provider not configured.")
        return await self.tts_provider.synthesize(text, language, voice_id)

    def is_voice_enabled(self) -> bool:
        return self.stt_provider is not None and self.tts_provider is not None

    @property
    def stt_name(self) -> str:
        return self.stt_provider.name if self.stt_provider else "none"

    @property
    def tts_name(self) -> str:
        return self.tts_provider.name if self.tts_provider else "none"


voice_service = VoiceService()
