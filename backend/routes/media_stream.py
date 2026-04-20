"""Real-time Twilio Media Streams WebSocket endpoint.

Replaces the turn-based TwiML Gather flow with a bi-directional WebSocket
that pipes mu-law audio both ways. Gives sub-second latency once STT/TTS
finish. Falls back to existing /webhook/gather if the stream fails to
connect (Twilio behaviour).
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from services.ai_orchestrator import ai_orchestrator
from services.voice_service import voice_service
from utils.db import db, prepare_for_mongo
from models.call import ConversationState, CallSummary
from datetime import datetime, timezone
import asyncio
import base64
import audioop
import wave
import io
import json
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Media Stream"])


# ------------------------- audio helpers -------------------------

def mulaw_to_wav(mulaw_bytes: bytes) -> bytes:
    """Convert mu-law 8 kHz audio to 16 kHz PCM WAV for Whisper."""
    linear_pcm = audioop.ulaw2lin(mulaw_bytes, 2)
    resampled, _ = audioop.ratecv(linear_pcm, 2, 1, 8000, 16000, None)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(resampled)
    return buf.getvalue()


def mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    """Convert MP3 (edge-tts output) to mu-law 8 kHz for Twilio."""
    import subprocess
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        f.write(mp3_bytes)
        mp3_path = f.name
    out_path = mp3_path.replace(".mp3", ".raw")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", mp3_path, "-ar", "8000", "-ac", "1", "-f", "mulaw", out_path],
            capture_output=True, check=True,
        )
        with open(out_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(mp3_path):
            os.unlink(mp3_path)
        if os.path.exists(out_path):
            os.unlink(out_path)


def is_speech(mulaw_chunk: bytes, threshold: int = 200) -> bool:
    """Simple energy-based voice-activity detection."""
    linear = audioop.ulaw2lin(mulaw_chunk, 2)
    return audioop.rms(linear, 2) > threshold


# ------------------------- websocket endpoint -------------------------

SILENCE_THRESHOLD = 200
SILENCE_CHUNKS_NEEDED = 25   # ~0.5 s of silence at 20 ms chunks
MIN_SPEECH_BYTES = 160 * 10  # ~0.2 s of speech before processing


@router.websocket("/ws/media-stream/{call_id}")
async def media_stream(websocket: WebSocket, call_id: str):
    await websocket.accept()

    stream_sid = None
    audio_buffer = bytearray()
    silence_chunks = 0
    speech_detected = False
    processing = False

    # Look up the call to resolve campaign + language
    call_doc = await db.calls.find_one({"id": call_id}, {"_id": 0})
    if not call_doc:
        await websocket.close()
        return

    state_doc = await db.conversation_states.find_one({"call_id": call_id}, {"_id": 0})
    if not state_doc:
        await websocket.close()
        return

    state = ConversationState(**state_doc)
    campaign = await db.campaigns.find_one({"id": call_doc["campaign_id"]}, {"_id": 0})
    if not campaign:
        await websocket.close()
        return

    language = state.language_detected or campaign.get("language", "indian_english")

    async def send_audio_to_caller(text: str):
        """TTS the text and stream back to Twilio as mu-law frames."""
        nonlocal processing
        try:
            mp3_bytes = await voice_service.text_to_speech(text, language)
            mulaw_bytes = mp3_to_mulaw(mp3_bytes)

            chunk_size = 320  # 20 ms at 8 kHz mu-law
            for i in range(0, len(mulaw_bytes), chunk_size):
                chunk = mulaw_bytes[i : i + chunk_size]
                payload = base64.b64encode(chunk).decode()
                await websocket.send_json({
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": payload},
                })
                await asyncio.sleep(0.02)

            await websocket.send_json({
                "event": "mark",
                "streamSid": stream_sid,
                "mark": {"name": "response_done"},
            })
        except Exception as e:
            logger.error(f"send_audio_to_caller error: {e}")
        finally:
            processing = False

    async def process_speech(audio_bytes: bytes):
        """STT → AI → TTS round trip, persisting state + closing call if needed."""
        nonlocal processing, state
        processing = True
        try:
            wav_bytes = mulaw_to_wav(bytes(audio_bytes))
            transcribed = await voice_service.speech_to_text(io.BytesIO(wav_bytes), language)
            if not transcribed or len(transcribed.strip()) < 2:
                processing = False
                return

            response_text, should_end = await ai_orchestrator.process_turn(
                user_input=transcribed,
                campaign_goal=campaign["goal"],
                language=language,
                conversation_state=state,
            )

            await db.conversation_states.update_one(
                {"call_id": call_id}, {"$set": prepare_for_mongo(state.model_dump())}
            )

            await send_audio_to_caller(response_text)

            if should_end:
                await db.calls.update_one(
                    {"id": call_id},
                    {"$set": {
                        "status": "completed",
                        "ended_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                from routes.phone_calls import _determine_outcome
                outcome = _determine_outcome(state)
                await db.call_outcomes.insert_one(prepare_for_mongo(outcome.model_dump()))
                summary_text = await ai_orchestrator.generate_call_summary(state)
                summary = CallSummary(call_id=call_id, summary_text=summary_text, key_points=[])
                await db.call_summaries.insert_one(prepare_for_mongo(summary.model_dump()))
                await asyncio.sleep(2)
                await websocket.close()
        except Exception as e:
            logger.error(f"process_speech error: {e}")
            processing = False

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")

            if event == "connected":
                logger.info(f"Media stream connected for call {call_id}")

            elif event == "start":
                stream_sid = data["streamSid"]
                logger.info(f"Stream started: {stream_sid}")

                if state.current_turn == 0:
                    greeting, _should_end = await ai_orchestrator.process_turn(
                        user_input="[Call connected. Greet briefly.]",
                        campaign_goal=campaign["goal"],
                        language=language,
                        conversation_state=state,
                    )
                    await db.conversation_states.update_one(
                        {"call_id": call_id}, {"$set": prepare_for_mongo(state.model_dump())}
                    )
                    processing = True
                    asyncio.create_task(send_audio_to_caller(greeting))

            elif event == "media":
                if processing:
                    continue

                track = data["media"].get("track", "inbound")
                if track != "inbound":
                    continue

                chunk = base64.b64decode(data["media"]["payload"])

                if is_speech(chunk, SILENCE_THRESHOLD):
                    speech_detected = True
                    silence_chunks = 0
                    audio_buffer.extend(chunk)
                elif speech_detected:
                    silence_chunks += 1
                    audio_buffer.extend(chunk)

                    if silence_chunks >= SILENCE_CHUNKS_NEEDED:
                        if len(audio_buffer) > MIN_SPEECH_BYTES:
                            audio_to_process = bytes(audio_buffer)
                            audio_buffer.clear()
                            speech_detected = False
                            silence_chunks = 0
                            asyncio.create_task(process_speech(audio_to_process))
                        else:
                            audio_buffer.clear()
                            speech_detected = False
                            silence_chunks = 0

            elif event == "stop":
                logger.info(f"Stream stopped for call {call_id}")
                break

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for call {call_id}")
    except Exception as e:
        logger.error(f"Media stream loop error: {e}")
