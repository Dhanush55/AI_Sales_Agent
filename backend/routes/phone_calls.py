"""Real phone call routes with Twilio TwiML webhooks."""
from fastapi import APIRouter, HTTPException, Depends, Request, Form, status
from fastapi.responses import Response
from models.call import Call, ConversationState, CallOutcome, CallSummary
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from services.ai_orchestrator import ai_orchestrator
from services.voice_service import voice_service
from services.telephony_service import telephony_service
from config import settings
from datetime import datetime, timezone
from typing import Optional
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/phone", tags=["Phone Calls"])


@router.get("/status")
async def phone_status():
    """Returns voice/telephony configuration status."""
    return {
        "voice_enabled": voice_service.is_voice_enabled(),
        "stt_provider": voice_service.stt_name,
        "tts_provider": voice_service.tts_name,
        "telephony_provider": telephony_service.provider_name,
        "telephony_configured": telephony_service.is_configured(),
    }


@router.post("/call")
async def initiate_manual_call(
    campaign_id: str,
    lead_id: str,
    user_id: str = Depends(get_current_user),
):
    """Initiate a manual phone call for a single lead."""
    if not telephony_service.is_configured():
        raise HTTPException(400, "Telephony not configured.")

    campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    lead = await db.leads.find_one({"id": lead_id, "campaign_id": campaign_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")

    webhook_url = f"{settings.APP_BASE_URL}/api/phone/webhook/answer?campaign_id={campaign_id}&lead_id={lead_id}"
    status_url = f"{settings.APP_BASE_URL}/api/phone/webhook/status"

    result = await telephony_service.provider.initiate_call(lead["phone"], webhook_url, status_url)

    call = Call(
        campaign_id=campaign_id,
        lead_id=lead_id,
        status="in_progress",
        call_source="manual",
        twilio_call_sid=result["call_sid"],
    )
    await db.calls.insert_one(prepare_for_mongo(call.model_dump()))

    state = ConversationState(call_id=call.id, language_detected=campaign["language"])
    await db.conversation_states.insert_one(prepare_for_mongo(state.model_dump()))

    await db.leads.update_one({"id": lead_id}, {"$set": {"status": "contacted"}})

    return {"call_id": call.id, "call_sid": result["call_sid"], "status": "initiated"}


def _twiml_response(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


LANG_TO_TWILIO = {
    "indian_english": "en-IN",
    "hindi": "hi-IN",
    "kannada": "kn-IN",
    "tamil": "ta-IN",
}


@router.post("/webhook/answer")
async def webhook_answer(campaign_id: str, lead_id: str, request: Request):
    """Twilio answer webhook - returns greeting + Gather."""
    from twilio.twiml.voice_response import VoiceResponse, Gather

    form = await request.form()
    call_sid = form.get("CallSid", "")

    call = await db.calls.find_one({"twilio_call_sid": call_sid}, {"_id": 0})
    campaign = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})

    language = campaign["language"] if campaign else "indian_english"
    twilio_lang = LANG_TO_TWILIO.get(language, "en-IN")

    # Initial greeting - simple opener
    greetings = {
        "indian_english": "Hello, am I speaking with the right person? I have a quick question.",
        "hindi": "Namaste, kya main sahi vyakti se baat kar raha hoon? Mujhe ek chhota sawaal hai.",
        "kannada": "Namaskara, naanu sariyaada vyaktiya jote matadutidane? Nanage ondu prashne ide.",
        "tamil": "Vanakkam, naan sariyana nabarudan pesukirena? Enakku oru kelvi irukku.",
    }
    greeting = greetings.get(language, greetings["indian_english"])

    response = VoiceResponse()
    gather = Gather(
        input="speech",
        language=twilio_lang,
        timeout=5,
        speech_timeout="auto",
        action=f"{settings.APP_BASE_URL}/api/phone/webhook/gather?call_id={call['id'] if call else ''}",
        method="POST",
    )
    gather.say(greeting, language=twilio_lang)
    response.append(gather)
    response.say("I did not hear anything. Goodbye.", language=twilio_lang)
    response.hangup()

    return _twiml_response(str(response))


@router.post("/webhook/gather")
async def webhook_gather(call_id: str, request: Request):
    """Twilio gather webhook - processes speech and returns next TwiML."""
    from twilio.twiml.voice_response import VoiceResponse, Gather

    form = await request.form()
    speech_result = form.get("SpeechResult", "")
    confidence = float(form.get("Confidence", "0") or 0)

    call = await db.calls.find_one({"id": call_id}, {"_id": 0})
    if not call:
        response = VoiceResponse()
        response.hangup()
        return _twiml_response(str(response))

    campaign = await db.campaigns.find_one({"id": call["campaign_id"]}, {"_id": 0})
    state_doc = await db.conversation_states.find_one({"call_id": call_id}, {"_id": 0})
    if not state_doc or not campaign:
        response = VoiceResponse()
        response.hangup()
        return _twiml_response(str(response))

    conversation_state = ConversationState(**state_doc)
    user_input = speech_result if speech_result and confidence >= 0.3 else "[User is silent]"

    agent_response, should_end = await ai_orchestrator.process_turn(
        user_input=user_input,
        campaign_goal=campaign["goal"],
        language=campaign["language"],
        conversation_state=conversation_state,
    )

    await db.conversation_states.update_one(
        {"call_id": call_id}, {"$set": prepare_for_mongo(conversation_state.model_dump())}
    )

    language = campaign["language"]
    twilio_lang = LANG_TO_TWILIO.get(language, "en-IN")

    response = VoiceResponse()
    response.say(agent_response, language=twilio_lang)

    if should_end:
        response.hangup()
    else:
        gather = Gather(
            input="speech",
            language=twilio_lang,
            timeout=5,
            speech_timeout="auto",
            action=f"{settings.APP_BASE_URL}/api/phone/webhook/gather?call_id={call_id}",
            method="POST",
        )
        response.append(gather)
        response.hangup()

    return _twiml_response(str(response))


@router.post("/webhook/status")
async def webhook_status(request: Request):
    """Twilio status callback - finalizes completed calls."""
    form = await request.form()
    call_sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    call_duration = form.get("CallDuration")

    call = await db.calls.find_one({"twilio_call_sid": call_sid}, {"_id": 0})
    if not call:
        return {"ok": True}

    if call_status == "completed":
        duration = int(call_duration) if call_duration else 0
        await db.calls.update_one(
            {"twilio_call_sid": call_sid},
            {"$set": {
                "status": "completed",
                "duration": duration,
                "ended_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        state_doc = await db.conversation_states.find_one({"call_id": call["id"]}, {"_id": 0})
        if state_doc:
            state = ConversationState(**state_doc)
            outcome = _determine_outcome(state)
            await db.call_outcomes.insert_one(prepare_for_mongo(outcome.model_dump()))
            summary_text = await ai_orchestrator.generate_call_summary(state)
            summary = CallSummary(call_id=call["id"], summary_text=summary_text)
            await db.call_summaries.insert_one(prepare_for_mongo(summary.model_dump()))

            # Map outcome to lead status
            lead_status_map = {
                "interested": "interested",
                "not_interested": "not_interested",
                "busy": "callback",
                "callback_scheduled": "callback",
                "no_answer": "pending",
            }
            await db.leads.update_one(
                {"id": call["lead_id"]},
                {"$set": {"status": lead_status_map.get(outcome.outcome, "contacted")}},
            )

        # Chain next dialer call if part of a running session
        if call.get("dialer_session_id"):
            import asyncio
            from routes.dialer import _dial_next
            session = await db.dialer_sessions.find_one({"id": call["dialer_session_id"]}, {"_id": 0})
            if session and session["status"] == "running":
                delay = session.get("delay_seconds", 60)

                async def delayed_next():
                    await asyncio.sleep(delay)
                    await _dial_next(session["id"])

                asyncio.create_task(delayed_next())
    elif call_status in ("failed", "no-answer", "busy", "canceled"):
        await db.calls.update_one(
            {"twilio_call_sid": call_sid},
            {"$set": {"status": "failed", "ended_at": datetime.now(timezone.utc).isoformat()}},
        )

    return {"ok": True}


def _determine_outcome(state: ConversationState) -> CallOutcome:
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
        notes=f"Call completed after {state.current_turn} turns",
    )
