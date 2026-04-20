"""Real phone call routes. Supports Twilio + Exotel (via ExoML) webhooks."""
from fastapi import APIRouter, HTTPException, Depends, Request
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
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/phone", tags=["Phone Calls"])


@router.get("/status")
async def phone_status():
    return {
        "voice_enabled": voice_service.is_voice_enabled(),
        "stt_provider": voice_service.stt_name,
        "tts_provider": voice_service.tts_name,
        "telephony_provider": telephony_service.provider_name,
        "telephony_configured": telephony_service.is_configured(),
    }


# ------------------------------------------------------------------
# Backward-compat helpers for the twilio_call_sid → call_sid rename
# ------------------------------------------------------------------

async def _find_call_by_sid(sid: str) -> Optional[dict]:
    """Look up a call by the new `call_sid` field, falling back to the legacy
    `twilio_call_sid` for any documents written before the rename."""
    if not sid:
        return None
    call = await db.calls.find_one({"call_sid": sid}, {"_id": 0})
    if call:
        return call
    return await db.calls.find_one({"twilio_call_sid": sid}, {"_id": 0})


async def _update_call_by_sid(sid: str, update: dict) -> None:
    """Update a call matched by call_sid OR legacy twilio_call_sid."""
    result = await db.calls.update_one({"call_sid": sid}, update)
    if result.matched_count == 0:
        await db.calls.update_one({"twilio_call_sid": sid}, update)


# ------------------------------------------------------------------

@router.post("/call")
async def initiate_manual_call(
    campaign_id: str,
    lead_id: str,
    user_id: str = Depends(get_current_user),
):
    if not telephony_service.is_configured():
        raise HTTPException(400, "Telephony not configured.")

    campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    lead = await db.leads.find_one({"id": lead_id, "campaign_id": campaign_id}, {"_id": 0})
    if not lead:
        raise HTTPException(404, "Lead not found")

    # Provider-specific answer webhook path
    prov = telephony_service.provider_name
    answer_path = "exotel/answer" if prov == "exotel" else "webhook/answer"
    status_path = "exotel/status" if prov == "exotel" else "webhook/status"
    webhook_url = f"{settings.APP_BASE_URL}/api/phone/{answer_path}?campaign_id={campaign_id}&lead_id={lead_id}"
    status_url = f"{settings.APP_BASE_URL}/api/phone/{status_path}"

    result = await telephony_service.provider.initiate_call(lead["phone"], webhook_url, status_url)

    call = Call(
        campaign_id=campaign_id,
        lead_id=lead_id,
        status="in_progress",
        call_source="manual",
        call_sid=result["call_sid"],
    )
    await db.calls.insert_one(prepare_for_mongo(call.model_dump()))
    state = ConversationState(call_id=call.id, language_detected=campaign["language"])
    await db.conversation_states.insert_one(prepare_for_mongo(state.model_dump()))
    await db.leads.update_one({"id": lead_id}, {"$set": {"status": "contacted"}})

    return {"call_id": call.id, "call_sid": result["call_sid"], "status": "initiated"}


def _twiml_response(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


def _exoml_response(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


def _build_stream_twiml(call_id: str) -> str:
    from twilio.twiml.voice_response import VoiceResponse, Connect
    ws_url = settings.APP_BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_url}/ws/media-stream/{call_id}"
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)
    return str(response)


def _build_stream_exoml(call_id: str) -> str:
    ws_url = settings.APP_BASE_URL.replace("https://", "wss://").replace("http://", "ws://")
    stream_url = f"{ws_url}/ws/media-stream/{call_id}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<Response><Connect><Stream url="{stream_url}"/></Connect></Response>'
    )


# ------------------------------------------------------------------
# Twilio webhooks
# ------------------------------------------------------------------

@router.post("/webhook/answer")
async def webhook_answer(campaign_id: str, lead_id: str, request: Request):
    """Twilio answer webhook - opens a bi-directional Media Stream to our WS."""
    from twilio.twiml.voice_response import VoiceResponse

    form = await request.form()
    sid = form.get("CallSid", "")

    call = await _find_call_by_sid(sid)
    if not call:
        # Fallback: find by campaign_id + lead_id + status=in_progress
        call = await db.calls.find_one(
            {"campaign_id": campaign_id, "lead_id": lead_id, "status": "in_progress"},
            {"_id": 0},
            sort=[("started_at", -1)],
        )
        # Best-effort backfill of the sid on the record we found
        if call and sid:
            await db.calls.update_one({"id": call["id"]}, {"$set": {"call_sid": sid}})

    if not call:
        r = VoiceResponse()
        r.hangup()
        return _twiml_response(str(r))

    return _twiml_response(_build_stream_twiml(call["id"]))


@router.post("/webhook/status")
async def webhook_status(request: Request):
    """Twilio status callback - finalizes completed calls."""
    form = await request.form()
    sid = form.get("CallSid", "")
    call_status = form.get("CallStatus", "")
    call_duration = form.get("CallDuration")
    await _finalize_call(sid, call_status, call_duration,
                         failed_statuses={"failed", "no-answer", "busy", "canceled"})
    return {"ok": True}


# ------------------------------------------------------------------
# Exotel webhooks
# ------------------------------------------------------------------

@router.post("/exotel/answer")
async def exotel_answer(campaign_id: str, lead_id: str, request: Request):
    """Exotel answer webhook - returns ExoML with <Connect><Stream>."""
    form = await request.form()
    sid = form.get("CallSid", "")

    call = await _find_call_by_sid(sid)
    if not call:
        call = await db.calls.find_one(
            {"campaign_id": campaign_id, "lead_id": lead_id, "status": "in_progress"},
            {"_id": 0},
            sort=[("started_at", -1)],
        )
        if call and sid:
            await db.calls.update_one({"id": call["id"]}, {"$set": {"call_sid": sid}})

    if not call:
        return _exoml_response('<?xml version="1.0" encoding="UTF-8"?><Response><Reject/></Response>')

    return _exoml_response(_build_stream_exoml(call["id"]))


@router.post("/exotel/status")
async def exotel_status(request: Request):
    """Exotel status callback - same finalization as Twilio, different field
    names & status vocabulary."""
    # Exotel can POST JSON or form; handle both.
    sid = ""
    status_value = ""
    duration = None
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
        except Exception:
            body = {}
        sid = body.get("CallSid", "") or body.get("CallSidReturnedByExotel", "")
        status_value = body.get("Status", "")
        duration = body.get("Duration") or body.get("ConversationDuration")
    else:
        form = await request.form()
        sid = form.get("CallSid", "")
        status_value = form.get("Status", "")
        duration = form.get("Duration") or form.get("ConversationDuration")

    await _finalize_call(
        sid, status_value, duration,
        failed_statuses={"failed", "no-answer", "busy", "canceled"},
    )
    return {"ok": True}


# ------------------------------------------------------------------
# Shared finalization
# ------------------------------------------------------------------

async def _finalize_call(sid: str, call_status: str, duration_raw, failed_statuses: set):
    call = await _find_call_by_sid(sid)
    if not call:
        return

    if call_status == "completed":
        duration = 0
        if duration_raw is not None:
            try:
                duration = int(duration_raw)
            except (TypeError, ValueError):
                duration = 0
        await _update_call_by_sid(sid, {"$set": {
            "status": "completed",
            "duration": duration,
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }})

        state_doc = await db.conversation_states.find_one({"call_id": call["id"]}, {"_id": 0})
        if state_doc:
            state = ConversationState(**state_doc)
            outcome = _determine_outcome(state)
            await db.call_outcomes.insert_one(prepare_for_mongo(outcome.model_dump()))
            summary_text = await ai_orchestrator.generate_call_summary(state)
            summary = CallSummary(call_id=call["id"], summary_text=summary_text)
            await db.call_summaries.insert_one(prepare_for_mongo(summary.model_dump()))

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

        if call.get("dialer_session_id"):
            from routes.dialer import _dial_next
            session = await db.dialer_sessions.find_one({"id": call["dialer_session_id"]}, {"_id": 0})
            if session and session["status"] == "running":
                delay = session.get("delay_seconds", 60)

                async def delayed_next():
                    await asyncio.sleep(delay)
                    await _dial_next(session["id"])

                asyncio.create_task(delayed_next())

    elif call_status in failed_statuses:
        await _update_call_by_sid(sid, {"$set": {
            "status": "failed",
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }})


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
