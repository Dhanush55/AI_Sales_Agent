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
    "telugu": "te",
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


class GroqWhisperSTT(STTProvider):
    """Ultra-fast cloud STT via Groq's whisper-large-v3-turbo (~200x realtime).

    Drop-in replacement for faster-whisper with the same OpenAI-compatible API.
    Multilingual; auto-detects language if none given.
    """

    def __init__(self, api_key: str, model: str = "whisper-large-v3-turbo"):
        self.api_key = api_key
        self.model = model

    @property
    def name(self) -> str:
        return "groq_whisper"

    async def transcribe(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key, base_url="https://api.groq.com/openai/v1")
        whisper_lang = LANG_MAP.get(language, None) if language else None
        # Groq SDK requires (filename, bytes) tuple
        audio_bytes = audio_data.read()
        file_tuple = ("recording.wav", audio_bytes, "audio/wav")
        transcription = await client.audio.transcriptions.create(
            model=self.model,
            file=file_tuple,
            language=whisper_lang,
            temperature=0.0,
        )
        return transcription.text or ""


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


class SarvamSTT(STTProvider):
    """Sarvam AI STT — best accuracy for Kannada/Tamil/Telugu/Hindi."""

    LANG_CODE = {
        "kannada": "kn-IN",
        "tamil": "ta-IN",
        "telugu": "te-IN",
        "hindi": "hi-IN",
        "indian_english": "en-IN",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "sarvam_stt"

    async def transcribe(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        import httpx, base64
        audio_bytes = audio_data.read()
        lang_code = self.LANG_CODE.get(language or "indian_english", "en-IN")
        payload = {
            "language_code": lang_code,
            "model": "saarika:v2.5",
            "audio": base64.b64encode(audio_bytes).decode(),
            "with_timestamps": False,
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.sarvam.ai/speech-to-text",
                json=payload,
                headers={"api-subscription-key": self.api_key},
            )
            resp.raise_for_status()
            return resp.json().get("transcript", "")


class SarvamTTS(TTSProvider):
    """Sarvam AI TTS — most natural Indian language voices."""

    VOICE_MAP = {
        "kannada": "anushka",       # Kannada female
        "tamil": "vidya",           # Tamil female
        "telugu": "arya",           # Telugu female
        "hindi": "manisha",         # Hindi female (bulbul:v2)
        "indian_english": "abhilash", # English male (bulbul:v2)
    }
    LANG_CODE = {
        "kannada": "kn-IN",
        "tamil": "ta-IN",
        "telugu": "te-IN",
        "hindi": "hi-IN",
        "indian_english": "en-IN",
    }

    def __init__(self, api_key: str):
        self.api_key = api_key

    @property
    def name(self) -> str:
        return "sarvam_tts"

    async def synthesize(self, text: str, language: str, voice_id: Optional[str] = None) -> bytes:
        import httpx, base64
        speaker = voice_id or self.VOICE_MAP.get(language, "anushka")
        lang_code = self.LANG_CODE.get(language, "en-IN")
        payload = {
            "inputs": [text],
            "target_language_code": lang_code,
            "speaker": speaker,
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.5,
            "speech_sample_rate": 22050,
            "enable_preprocessing": True,
            "model": "bulbul:v2",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.sarvam.ai/text-to-speech",
                json=payload,
                headers={"api-subscription-key": self.api_key},
            )
            resp.raise_for_status()
            audios = resp.json().get("audios", [])
            if not audios:
                raise RuntimeError("Sarvam TTS returned no audio")
            return base64.b64decode(audios[0])


class EdgeTTSProvider(TTSProvider):
    """Free local TTS using Microsoft Edge TTS (edge-tts)."""

    VOICE_MAP = {
        "indian_english": "en-IN-NeerjaNeural",
        "hindi": "hi-IN-SwaraNeural",
        "kannada": "kn-IN-SapnaNeural",
        "tamil": "ta-IN-PallaviNeural",
        "telugu": "te-IN-ShrutiNeural",
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
        # Auto-prefer Groq Whisper when key is present — it's ~10-20x faster than
        # local faster-whisper on commodity hardware. Override with STT_PROVIDER env.
        groq_key = os.environ.get("GROQ_API_KEY", "")
        sarvam_key = os.environ.get("SARVAM_API_KEY", "")
        default_stt = "sarvam" if sarvam_key else ("groq_whisper" if groq_key else "faster_whisper")
        stt_type = os.environ.get("STT_PROVIDER", default_stt).lower()
        default_tts = "sarvam" if sarvam_key else "edge_tts"
        tts_type = os.environ.get("TTS_PROVIDER", default_tts).lower()

        if stt_type == "sarvam" and sarvam_key:
            self.stt_provider = SarvamSTT(sarvam_key)
            logger.info("STT: Sarvam (saarika:v2)")
        elif stt_type == "groq_whisper" and groq_key:
            model = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")
            self.stt_provider = GroqWhisperSTT(groq_key, model)
            logger.info(f"STT: Groq Whisper ({model})")
        elif stt_type == "faster_whisper":
            model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")
            self.stt_provider = FasterWhisperSTT(model_size)
            logger.info(f"STT: faster-whisper ({model_size})")
        elif stt_type == "openai_whisper":
            api_key = os.environ.get("EMERGENT_LLM_KEY") or os.environ.get("OPENAI_API_KEY")
            if api_key:
                self.stt_provider = OpenAIWhisperSTT(api_key)
                logger.info("STT: OpenAI Whisper")

        # Fallback chain: if requested provider failed, try faster-whisper
        if self.stt_provider is None:
            try:
                model_size = os.environ.get("WHISPER_MODEL_SIZE", "base")
                self.stt_provider = FasterWhisperSTT(model_size)
                logger.info(f"STT fallback: faster-whisper ({model_size})")
            except Exception as e:
                logger.error(f"All STT providers failed: {e}")

        if tts_type == "sarvam" and sarvam_key:
            self.tts_provider = SarvamTTS(sarvam_key)
            logger.info("TTS: Sarvam (bulbul:v1)")
        elif tts_type == "edge_tts":
            self.tts_provider = EdgeTTSProvider()
            logger.info("TTS: edge-tts (Microsoft neural)")
        elif tts_type == "elevenlabs":
            api_key = os.environ.get("ELEVENLABS_API_KEY")
            if api_key:
                self.tts_provider = ElevenLabsTTS(api_key)

        if self.tts_provider is None:
            self.tts_provider = EdgeTTSProvider()
            logger.info("TTS fallback: edge-tts")

    async def speech_to_text(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        if not self.stt_provider:
            raise RuntimeError("STT provider not configured.")
        # Buffer the audio so we can retry with a fallback if Groq fails
        audio_bytes = audio_data.read() if hasattr(audio_data, "read") else audio_data
        try:
            return await self.stt_provider.transcribe(io.BytesIO(audio_bytes), language)
        except Exception as e:
            logger.warning(f"Primary STT ({self.stt_provider.name}) failed: {e} — falling back")
            # On primary failure, try faster-whisper once as a safety net
            if self.stt_provider.name != "faster_whisper":
                try:
                    fallback = FasterWhisperSTT(os.environ.get("WHISPER_MODEL_SIZE", "base"))
                    return await fallback.transcribe(io.BytesIO(audio_bytes), language)
                except Exception as e2:
                    logger.error(f"Fallback STT also failed: {e2}")
            raise

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
