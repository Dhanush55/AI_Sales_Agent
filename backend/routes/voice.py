from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from fastapi.responses import Response
from utils.security import get_current_user
from services.voice_service import voice_service
from pydantic import BaseModel
from typing import Optional
import logging
import io

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["Voice"])

class TTSRequest(BaseModel):
    text: str
    language: str
    voice_id: Optional[str] = None

@router.post("/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    language: Optional[str] = None,
    user_id: str = Depends(get_current_user)
):
    """Convert speech to text"""
    try:
        if not voice_service.is_voice_enabled():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Voice services not configured. Set STT_PROVIDER and required API keys."
            )
        
        # Read audio data
        audio_data = await audio.read()
        audio_file = io.BytesIO(audio_data)
        audio_file.name = audio.filename or "audio.wav"
        
        # Transcribe
        text = await voice_service.speech_to_text(audio_file, language)
        
        return {"text": text}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"STT error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Speech-to-text failed: {str(e)}"
        )

@router.post("/tts")
async def text_to_speech(
    request: TTSRequest,
    user_id: str = Depends(get_current_user)
):
    """Convert text to speech"""
    try:
        if not voice_service.is_voice_enabled():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Voice services not configured. Set TTS_PROVIDER and required API keys."
            )
        
        # Synthesize speech
        audio_data = await voice_service.text_to_speech(
            text=request.text,
            language=request.language,
            voice_id=request.voice_id
        )
        
        # Return audio as MP3
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "attachment; filename=speech.mp3"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text-to-speech failed: {str(e)}"
        )

@router.get("/status")
async def voice_status(user_id: str = Depends(get_current_user)):
    """Check voice services status"""
    return {
        "voice_enabled": voice_service.is_voice_enabled(),
        "stt_available": voice_service.stt_provider is not None,
        "tts_available": voice_service.tts_provider is not None
    }
