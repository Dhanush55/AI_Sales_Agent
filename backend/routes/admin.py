"""Admin routes - platform-wide user and stats management."""
from fastapi import APIRouter, HTTPException, Depends, Query
from utils.security import get_current_user, hash_password
from utils.db import db
from datetime import datetime, timezone, timedelta
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["Admin"])


async def require_admin(user_id: str = Depends(get_current_user)) -> str:
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user or not user.get("is_admin"):
        raise HTTPException(403, "Admin access required")
    return user_id


async def _user_stats(user_id: str, month_start: str) -> dict:
    camps = await db.campaigns.find({"user_id": user_id}, {"_id": 0, "id": 1}).to_list(10000)
    camp_ids = [c["id"] for c in camps]
    lead_count_task = db.leads.count_documents({"campaign_id": {"$in": camp_ids}})
    call_count_task = db.calls.count_documents({"campaign_id": {"$in": camp_ids}})
    calls_month_task = db.calls.count_documents(
        {"campaign_id": {"$in": camp_ids}, "started_at": {"$gte": month_start}}
    )
    lead_count, call_count, calls_month = await asyncio.gather(
        lead_count_task, call_count_task, calls_month_task
    )
    return {
        "campaign_count": len(camp_ids),
        "lead_count": lead_count,
        "call_count": call_count,
        "calls_this_month": calls_month,
    }


@router.get("/users")
async def list_users(_admin: str = Depends(require_admin)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(10000)
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    results = []
    for u in users:
        stats = await _user_stats(u["id"], month_start)
        results.append({
            "id": u["id"],
            "email": u["email"],
            "company_name": u.get("company_name", ""),
            "created_at": u.get("created_at"),
            "is_admin": u.get("is_admin", False),
            **stats,
        })
    return results


@router.get("/stats")
async def platform_stats(_admin: str = Depends(require_admin)):
    today_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).isoformat()

    total_users, total_campaigns, total_leads, total_calls, calls_today, active_dialers = await asyncio.gather(
        db.users.count_documents({}),
        db.campaigns.count_documents({}),
        db.leads.count_documents({}),
        db.calls.count_documents({}),
        db.calls.count_documents({"started_at": {"$gte": today_start}}),
        db.dialer_sessions.count_documents({"status": "running"}),
    )
    return {
        "total_users": total_users,
        "total_campaigns": total_campaigns,
        "total_leads": total_leads,
        "total_calls": total_calls,
        "calls_today": calls_today,
        "active_dialers": active_dialers,
    }


# ── TEMPORARY local recovery endpoint — REMOVE AFTER USE ──
@router.post("/_local_reset_password")
async def local_reset_password(
    email: str = Query(...),
    new_password: str = Query(...),
    secret: str = Query(...),
):
    """One-shot local password reset. Hard-coded secret; remove this route after recovery."""
    if secret != "recovery-2026-04-26":
        raise HTTPException(403, "bad secret")
    user = await db.users.find_one({"email": email})
    if not user:
        raise HTTPException(404, f"no user with email {email}")
    new_hash = hash_password(new_password)
    await db.users.update_one({"email": email}, {"$set": {"password_hash": new_hash}})
    return {"ok": True, "email": email, "user_id": user.get("id")}


@router.put("/users/{target_user_id}/toggle-admin")
async def toggle_admin(target_user_id: str, _admin: str = Depends(require_admin)):
    user = await db.users.find_one({"id": target_user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(404, "User not found")
    new_val = not bool(user.get("is_admin", False))
    await db.users.update_one({"id": target_user_id}, {"$set": {"is_admin": new_val}})
    user["is_admin"] = new_val
    return user
