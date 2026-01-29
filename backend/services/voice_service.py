from abc import ABC, abstractmethod
from typing import BinaryIO, Optional
import os

class STTProvider(ABC):
    """Abstract base class for Speech-to-Text providers"""
    
    @abstractmethod
    async def transcribe(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        """Transcribe audio to text"""
        pass

class TTSProvider(ABC):
    """Abstract base class for Text-to-Speech providers"""
    
    @abstractmethod
    async def synthesize(self, text: str, language: str, voice_id: Optional[str] = None) -> bytes:
        """Synthesize text to speech audio"""
        pass

class OpenAIWhisperSTT(STTProvider):
    """OpenAI Whisper STT implementation"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    async def transcribe(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        """Transcribe audio using OpenAI Whisper"""
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            
            # Map our language codes to Whisper language codes
            language_map = {
                "indian_english": "en",
                "hindi": "hi",
                "kannada": "kn",
                "tamil": "ta"
            }
            whisper_lang = language_map.get(language, "en") if language else None
            
            transcription = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_data,
                language=whisper_lang
            )
            
            return transcription.text
        except Exception as e:
            raise Exception(f"STT transcription failed: {str(e)}")

class ElevenLabsTTS(TTSProvider):
    """ElevenLabs TTS implementation"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Default voice IDs for different languages
        self.default_voices = {
            "indian_english": "21m00Tcm4TlvDq8ikWAM",  # Rachel - neutral English
            "hindi": "21m00Tcm4TlvDq8ikWAM",
            "kannada": "21m00Tcm4TlvDq8ikWAM",
            "tamil": "21m00Tcm4TlvDq8ikWAM"
        }
    
    async def synthesize(self, text: str, language: str, voice_id: Optional[str] = None) -> bytes:
        """Synthesize speech using ElevenLabs"""
        try:
            from elevenlabs import ElevenLabs
            from elevenlabs import VoiceSettings
            
            client = ElevenLabs(api_key=self.api_key)
            
            # Use provided voice_id or default for language
            voice = voice_id or self.default_voices.get(language, self.default_voices["indian_english"])
            
            # Generate audio
            audio_generator = client.text_to_speech.convert(
                text=text,
                voice_id=voice,
                model_id="eleven_multilingual_v2",
                voice_settings=VoiceSettings(
                    stability=0.7,
                    similarity_boost=0.8,
                    style=0.0,
                    use_speaker_boost=True
                )
            )
            
            # Collect audio data
            audio_data = b""
            for chunk in audio_generator:
                audio_data += chunk
            
            return audio_data
        except Exception as e:
            raise Exception(f"TTS synthesis failed: {str(e)}")

class VoiceService:
    """Voice service that manages STT and TTS providers"""
    
    def __init__(self):
        self.stt_provider: Optional[STTProvider] = None
        self.tts_provider: Optional[TTSProvider] = None
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize voice providers from environment config"""
        stt_provider_type = os.environ.get('STT_PROVIDER', 'openai_whisper')
        tts_provider_type = os.environ.get('TTS_PROVIDER', 'elevenlabs')
        
        # Initialize STT
        if stt_provider_type == 'openai_whisper':
            api_key = os.environ.get('EMERGENT_LLM_KEY') or os.environ.get('OPENAI_API_KEY')
            if api_key:
                self.stt_provider = OpenAIWhisperSTT(api_key)
        
        # Initialize TTS
        if tts_provider_type == 'elevenlabs':
            api_key = os.environ.get('ELEVENLABS_API_KEY')
            if api_key:
                self.tts_provider = ElevenLabsTTS(api_key)
    
    async def speech_to_text(self, audio_data: BinaryIO, language: Optional[str] = None) -> str:
        """Convert speech to text"""
        if not self.stt_provider:
            raise Exception("STT provider not configured. Set STT_PROVIDER and required API keys.")
        return await self.stt_provider.transcribe(audio_data, language)
    
    async def text_to_speech(self, text: str, language: str, voice_id: Optional[str] = None) -> bytes:
        """Convert text to speech"""
        if not self.tts_provider:
            raise Exception("TTS provider not configured. Set TTS_PROVIDER and required API keys.")
        return await self.tts_provider.synthesize(text, language, voice_id)
    
    def is_voice_enabled(self) -> bool:
        """Check if voice services are available"""
        return self.stt_provider is not None and self.tts_provider is not None

# Global voice service instance
voice_service = VoiceService()