from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from models.test_mode import TestModeInput, TestModeResponse
from models.call import Call, ConversationState, CallOutcome, CallSummary
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from services.ai_orchestrator import ai_orchestrator
from services.voice_service import voice_service
from datetime import datetime, timezone
from typing import Optional
import asyncio
import base64
import io
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/test-mode", tags=["Test Mode"])

@router.post("/chat", response_model=TestModeResponse)
async def test_mode_chat(input_data: TestModeInput, user_id: str = Depends(get_current_user)):
    """Test mode conversation endpoint"""
    try:
        # Verify campaign
        campaign = await db.campaigns.find_one(
            {"id": input_data.campaign_id, "user_id": user_id},
            {"_id": 0}
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        # Handle simulation inputs
        if input_data.simulate == "silence":
            user_input = "[User is silent]"
        elif input_data.simulate == "interruption":
            user_input = f"[User interrupts] {input_data.user_input}"
        else:
            user_input = input_data.user_input
        
        # Get or create conversation state
        if input_data.call_id:
            # Existing conversation
            state_doc = await db.conversation_states.find_one(
                {"call_id": input_data.call_id},
                {"_id": 0}
            )
            if not state_doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conversation not found"
                )
            conversation_state = ConversationState(**state_doc)
        else:
            # New conversation - create call
            call = Call(
                lead_id="test_lead",
                campaign_id=input_data.campaign_id
            )
            call_doc = prepare_for_mongo(call.model_dump())
            await db.calls.insert_one(call_doc)
            
            # Create conversation state
            conversation_state = ConversationState(
                call_id=call.id,
                language_detected=campaign["language"]
            )
            state_doc = prepare_for_mongo(conversation_state.model_dump())
            await db.conversation_states.insert_one(state_doc)
        
        # Process with AI orchestrator
        agent_response, should_end = await ai_orchestrator.process_turn(
            user_input=user_input,
            campaign_goal=campaign["goal"],
            language=campaign["language"],
            conversation_state=conversation_state,
            campaign=campaign,
        )
        
        # Update conversation state in DB
        updated_state_doc = prepare_for_mongo(conversation_state.model_dump())
        await db.conversation_states.update_one(
            {"call_id": conversation_state.call_id},
            {"$set": updated_state_doc}
        )
        
        # If call should end, finalize it
        if should_end:
            # Update call status
            await db.calls.update_one(
                {"id": conversation_state.call_id},
                {"$set": {
                    "status": "completed",
                    "ended_at": datetime.now(timezone.utc).isoformat(),
                    "duration": (conversation_state.current_turn * 30)
                }}
            )
            
            # Determine outcome
            outcome = _determine_outcome(conversation_state)
            outcome_doc = prepare_for_mongo(outcome.model_dump())
            await db.call_outcomes.insert_one(outcome_doc)
            
            # Generate summary
            summary_text = await ai_orchestrator.generate_call_summary(conversation_state)
            summary = CallSummary(
                call_id=conversation_state.call_id,
                summary_text=summary_text,
                key_points=[]
            )
            summary_doc = prepare_for_mongo(summary.model_dump())
            await db.call_summaries.insert_one(summary_doc)
        
        return TestModeResponse(
            call_id=conversation_state.call_id,
            agent_response=agent_response,
            should_end_call=should_end,
            conversation_state=conversation_state.model_dump()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Test mode error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Test mode failed: {str(e)}"
        )

@router.post("/voice-turn")
async def voice_turn_streaming(
    audio: UploadFile = File(...),
    campaign_id: str = Form(...),
    call_id: Optional[str] = Form(None),
    user_id: str = Depends(get_current_user),
):
    """Single-roundtrip streaming voice turn.

    Pipeline: STT → streaming LLM → sentence-by-sentence TTS, streamed back as
    Server-Sent Events. The browser gets the first audio chunk ~1s after the
    user finishes speaking instead of 4-9s with the old multi-step flow.

    SSE event types:
      transcript : {text}              — what the user said
      delta      : {text}              — incremental LLM text
      audio      : {b64, sentence}     — base64 MP3 for one sentence
      done       : {call_id, full_text, should_end_call, language}
      error      : {detail}
    """
    if not voice_service.is_voice_enabled():
        raise HTTPException(status_code=503, detail="Voice services not configured.")

    campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    audio_bytes = await audio.read()
    if len(audio_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty audio")

    # Get or create conversation state
    if call_id:
        state_doc = await db.conversation_states.find_one({"call_id": call_id}, {"_id": 0})
        if not state_doc:
            raise HTTPException(status_code=404, detail="Conversation not found")
        conversation_state = ConversationState(**state_doc)
    else:
        call = Call(lead_id="test_lead", campaign_id=campaign_id)
        call_doc = prepare_for_mongo(call.model_dump())
        await db.calls.insert_one(call_doc)
        conversation_state = ConversationState(call_id=call.id, language_detected=campaign["language"])
        state_doc = prepare_for_mongo(conversation_state.model_dump())
        await db.conversation_states.insert_one(state_doc)

    async def event_stream():
        def sse(event: str, data: dict) -> str:
            return f"event: {event}\ndata: {json.dumps(data)}\n\n"

        turn_metrics = {}  # collects stt_ms, llm_ms, tts_first_ms per turn

        try:
            # ── 1. STT ──
            language = campaign["language"]
            t0 = asyncio.get_event_loop().time()
            transcript = await voice_service.speech_to_text(io.BytesIO(audio_bytes), language)
            transcript = (transcript or "").strip()
            stt_ms = int((asyncio.get_event_loop().time() - t0) * 1000)
            turn_metrics["stt_ms"] = stt_ms
            logger.info(f"[voice-turn] STT {stt_ms}ms → '{transcript[:60]}'")

            if not transcript or len(transcript) < 2:
                yield sse("error", {"detail": "Empty transcript — could not hear clearly"})
                yield sse("done", {
                    "call_id": conversation_state.call_id,
                    "full_text": "",
                    "should_end_call": False,
                    "language": language,
                    "metrics": turn_metrics,
                })
                return

            yield sse("transcript", {"text": transcript})

            # ── 2. Streaming LLM + sentence-flushed TTS in parallel ──
            tts_tasks: list[asyncio.Task] = []
            tts_queue: asyncio.Queue = asyncio.Queue()
            full_text = ""
            should_end = False
            final_lang = language
            llm_start = asyncio.get_event_loop().time()
            tts_first_done = False

            async def synthesize_sentence(idx: int, sentence: str, lang: str):
                """Synthesize one sentence and push the audio bytes onto the queue."""
                nonlocal tts_first_done
                try:
                    ts0 = asyncio.get_event_loop().time()
                    audio_data = await voice_service.text_to_speech(sentence, lang)
                    ts_ms = int((asyncio.get_event_loop().time() - ts0) * 1000)
                    if not tts_first_done:
                        tts_first_done = True
                        turn_metrics["tts_first_ms"] = int((asyncio.get_event_loop().time() - llm_start) * 1000)
                    logger.info(f"[voice-turn] TTS#{idx} {ts_ms}ms ({len(audio_data)}B) '{sentence[:40]}'")
                    await tts_queue.put((idx, sentence, audio_data))
                except Exception as e:
                    logger.error(f"TTS failed for sentence {idx}: {e}")
                    await tts_queue.put((idx, sentence, None))

            async def llm_producer():
                """Consume LLM stream, kick off TTS per sentence, signal done."""
                nonlocal full_text, should_end, final_lang
                idx = 0
                async for ev in ai_orchestrator.stream_turn(
                    user_input=transcript,
                    campaign_goal=campaign["goal"],
                    language=language,
                    conversation_state=conversation_state,
                    campaign=campaign,
                ):
                    if ev["type"] == "delta":
                        # Forward token delta to client (UI shows partial text)
                        await tts_queue.put(("delta", ev["text"]))
                    elif ev["type"] == "sentence":
                        idx += 1
                        task = asyncio.create_task(
                            synthesize_sentence(idx, ev["text"], conversation_state.language_detected or language)
                        )
                        tts_tasks.append(task)
                    elif ev["type"] == "final":
                        full_text = ev["text"]
                        should_end = ev.get("should_end_call", False)
                        final_lang = ev.get("language", language)
                # signal end-of-llm
                await tts_queue.put(("__llm_done__", None))

            producer_task = asyncio.create_task(llm_producer())

            # Pump events out in order: deltas immediately, audio chunks in sentence order
            llm_done = False
            next_audio_idx = 1
            pending_audio: dict[int, tuple] = {}  # idx → (sentence, audio_bytes)

            while True:
                item = await tts_queue.get()
                tag = item[0]

                if tag == "delta":
                    yield sse("delta", {"text": item[1]})
                elif tag == "__llm_done__":
                    llm_done = True
                else:
                    # tag is an int (audio index)
                    idx, sentence, audio_data = item
                    pending_audio[idx] = (sentence, audio_data)

                # Flush any audio chunks now ready in order
                while next_audio_idx in pending_audio:
                    sentence, audio_data = pending_audio.pop(next_audio_idx)
                    if audio_data:
                        b64 = base64.b64encode(audio_data).decode("ascii")
                        yield sse("audio", {"sentence": sentence, "b64": b64})
                    next_audio_idx += 1

                # Exit when LLM finished AND all in-flight TTS tasks done AND queue drained
                if llm_done and all(t.done() for t in tts_tasks) and tts_queue.empty():
                    # also drain any audio that finished after llm_done
                    while next_audio_idx in pending_audio:
                        sentence, audio_data = pending_audio.pop(next_audio_idx)
                        if audio_data:
                            b64 = base64.b64encode(audio_data).decode("ascii")
                            yield sse("audio", {"sentence": sentence, "b64": b64})
                        next_audio_idx += 1
                    break

            await producer_task
            turn_metrics["llm_ms"] = int((asyncio.get_event_loop().time() - llm_start) * 1000)
            total_ms = turn_metrics.get("stt_ms", 0) + turn_metrics["llm_ms"]
            turn_metrics["total_ms"] = total_ms
            logger.info(f"[voice-turn] METRICS stt={turn_metrics.get('stt_ms')}ms llm={turn_metrics['llm_ms']}ms tts_first={turn_metrics.get('tts_first_ms')}ms total={total_ms}ms")

            # ── 3. Persist conversation state + metrics ──
            updated_state_doc = prepare_for_mongo(conversation_state.model_dump())
            await db.conversation_states.update_one(
                {"call_id": conversation_state.call_id},
                {"$set": updated_state_doc}
            )
            # Store per-turn latency metrics on the call document
            await db.calls.update_one(
                {"id": conversation_state.call_id},
                {"$push": {"turn_metrics": {
                    "turn": conversation_state.current_turn,
                    **turn_metrics,
                }}}
            )

            if should_end:
                await db.calls.update_one(
                    {"id": conversation_state.call_id},
                    {"$set": {
                        "status": "completed",
                        "ended_at": datetime.now(timezone.utc).isoformat(),
                        "duration": (conversation_state.current_turn * 30),
                    }}
                )
                outcome = _determine_outcome(conversation_state)
                await db.call_outcomes.insert_one(prepare_for_mongo(outcome.model_dump()))
                summary_text = await ai_orchestrator.generate_call_summary(conversation_state)
                summary = CallSummary(call_id=conversation_state.call_id, summary_text=summary_text, key_points=[])
                await db.call_summaries.insert_one(prepare_for_mongo(summary.model_dump()))

            yield sse("done", {
                "call_id": conversation_state.call_id,
                "full_text": full_text,
                "should_end_call": should_end,
                "language": final_lang,
                "metrics": turn_metrics,
            })

        except Exception as e:
            logger.error(f"voice-turn streaming error: {e}", exc_info=True)
            yield sse("error", {"detail": str(e)})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering if proxied
        },
    )


def _determine_outcome(state: ConversationState) -> CallOutcome:
    """Determine call outcome from conversation state"""
    if state.not_interested_count >= 1:
        outcome_type, is_qualified = "not_interested", False
    elif state.context.get("user_is_busy"):
        outcome_type, is_qualified = "busy", False
    elif state.current_turn >= 5:
        outcome_type, is_qualified = "interested", True
    else:
        outcome_type, is_qualified = "callback_scheduled", False
    
    return CallOutcome(
        call_id=state.call_id,
        outcome=outcome_type,
        is_qualified=is_qualified,
        notes=f"Conversation completed after {state.current_turn} turns"
    )