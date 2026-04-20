"""Auto-dialer routes - sequential outbound calling with pause/resume."""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from models.call import Call, ConversationState, DialerSession
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from services.telephony_service import telephony_service
from config import settings
from datetime import datetime, timezone
from pydantic import BaseModel
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/dialer", tags=["Dialer"])


class LaunchRequest(BaseModel):
    campaign_id: str
    delay_between_calls_seconds: int = 60


async def _dial_next(session_id: str):
    session = await db.dialer_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session or session["status"] != "running":
        return
    if session["current_index"] >= len(session["lead_ids"]):
        await db.dialer_sessions.update_one(
            {"id": session_id},
            {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}},
        )
        return

    lead_id = session["lead_ids"][session["current_index"]]
    lead = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    campaign = await db.campaigns.find_one({"id": session["campaign_id"]}, {"_id": 0})
    if not lead or not campaign:
        await db.dialer_sessions.update_one(
            {"id": session_id}, {"$inc": {"current_index": 1}}
        )
        asyncio.create_task(_dial_next(session_id))
        return

    webhook_url = (
        f"{settings.APP_BASE_URL}/api/phone/webhook/answer"
        f"?campaign_id={session['campaign_id']}&lead_id={lead_id}"
    )
    status_url = f"{settings.APP_BASE_URL}/api/phone/webhook/status"

    try:
        result = await telephony_service.provider.initiate_call(lead["phone"], webhook_url, status_url)
    except Exception as e:
        logger.error(f"Dialer call failed for lead {lead_id}: {e}")
        await db.dialer_sessions.update_one(
            {"id": session_id}, {"$inc": {"current_index": 1}}
        )
        asyncio.create_task(_dial_next(session_id))
        return

    call = Call(
        campaign_id=session["campaign_id"],
        lead_id=lead_id,
        status="in_progress",
        call_source="dialer",
        twilio_call_sid=result["call_sid"],
        dialer_session_id=session_id,
    )
    await db.calls.insert_one(prepare_for_mongo(call.model_dump()))
    state = ConversationState(call_id=call.id, language_detected=campaign["language"])
    await db.conversation_states.insert_one(prepare_for_mongo(state.model_dump()))
    await db.leads.update_one({"id": lead_id}, {"$set": {"status": "contacted"}})
    await db.dialer_sessions.update_one(
        {"id": session_id},
        {"$inc": {"calls_made": 1}, "$set": {"current_index": session["current_index"] + 1}},
    )


async def _delayed_dial_next(session_id: str, delay: int = 3):
    await asyncio.sleep(delay)
    await _dial_next(session_id)


async def _verify_session_ownership(session_id: str, user_id: str) -> dict:
    session = await db.dialer_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(404, "Session not found")
    campaign = await db.campaigns.find_one(
        {"id": session["campaign_id"], "user_id": user_id}, {"_id": 0}
    )
    if not campaign:
        raise HTTPException(403, "Access denied")
    return session


@router.post("/launch")
async def launch_dialer(
    req: LaunchRequest,
    background: BackgroundTasks,
    user_id: str = Depends(get_current_user),
):
    campaign = await db.campaigns.find_one(
        {"id": req.campaign_id, "user_id": user_id}, {"_id": 0}
    )
    if not campaign:
        raise HTTPException(404, "Campaign not found")

    existing = await db.dialer_sessions.find_one(
        {"campaign_id": req.campaign_id, "status": "running"}, {"_id": 0}
    )
    if existing:
        raise HTTPException(400, "A dialer session is already running for this campaign")

    leads = await db.leads.find(
        {"campaign_id": req.campaign_id, "status": "pending"}, {"_id": 0, "id": 1}
    ).to_list(10000)
    if not leads:
        raise HTTPException(400, "No pending leads to dial")

    session = DialerSession(
        user_id=user_id,
        campaign_id=req.campaign_id,
        lead_ids=[l["id"] for l in leads],
        delay_seconds=max(10, req.delay_between_calls_seconds),
    )
    await db.dialer_sessions.insert_one(prepare_for_mongo(session.model_dump()))

    background.add_task(_delayed_dial_next, session.id, 3)

    return {"session_id": session.id, "total_leads": len(leads), "status": "launched"}


@router.post("/{session_id}/pause")
async def pause_dialer(session_id: str, user_id: str = Depends(get_current_user)):
    await _verify_session_ownership(session_id, user_id)
    await db.dialer_sessions.update_one({"id": session_id}, {"$set": {"status": "paused"}})
    session = await db.dialer_sessions.find_one({"id": session_id}, {"_id": 0})
    return session


@router.post("/{session_id}/resume")
async def resume_dialer(
    session_id: str,
    background: BackgroundTasks,
    user_id: str = Depends(get_current_user),
):
    await _verify_session_ownership(session_id, user_id)
    await db.dialer_sessions.update_one({"id": session_id}, {"$set": {"status": "running"}})
    background.add_task(_dial_next, session_id)
    session = await db.dialer_sessions.find_one({"id": session_id}, {"_id": 0})
    return session


@router.get("/{session_id}")
async def get_dialer_session(session_id: str, user_id: str = Depends(get_current_user)):
    session = await _verify_session_ownership(session_id, user_id)
    return session


@router.get("/campaign/{campaign_id}")
async def get_campaign_dialer_session(campaign_id: str, user_id: str = Depends(get_current_user)):
    campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id}, {"_id": 0})
    if not campaign:
        raise HTTPException(404, "Campaign not found")
    session = await db.dialer_sessions.find_one(
        {"campaign_id": campaign_id}, {"_id": 0}, sort=[("started_at", -1)]
    )
    if not session:
        raise HTTPException(404, "No dialer session found for this campaign")
    return session
