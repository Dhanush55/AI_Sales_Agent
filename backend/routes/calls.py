from fastapi import APIRouter, HTTPException, Depends, status
from models.call import Call, CallOutcome, CallSummary
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/calls", tags=["Calls"])

@router.get("", response_model=List[Call])
async def get_calls(campaign_id: str = None, user_id: str = Depends(get_current_user)):
    """Get calls, optionally filtered by campaign"""
    try:
        query = {}
        if campaign_id:
            # Verify campaign belongs to user
            campaign = await db.campaigns.find_one(
                {"id": campaign_id, "user_id": user_id}
            )
            if not campaign:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Campaign not found"
                )
            query["campaign_id"] = campaign_id
        else:
            # Get all campaigns for user
            campaigns = await db.campaigns.find({"user_id": user_id}, {"_id": 0}).to_list(1000)
            campaign_ids = [c["id"] for c in campaigns]
            query["campaign_id"] = {"$in": campaign_ids}
        
        calls = await db.calls.find(query, {"_id": 0}).sort("started_at", -1).to_list(1000)
        return calls
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get calls error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch calls"
        )

@router.get("/{call_id}", response_model=Call)
async def get_call(call_id: str, user_id: str = Depends(get_current_user)):
    """Get a specific call"""
    try:
        call = await db.calls.find_one({"id": call_id}, {"_id": 0})
        if not call:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call not found"
            )
        
        # Verify access
        campaign = await db.campaigns.find_one(
            {"id": call["campaign_id"], "user_id": user_id}
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        return call
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get call error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch call"
        )

@router.get("/{call_id}/outcome", response_model=CallOutcome)
async def get_call_outcome(call_id: str, user_id: str = Depends(get_current_user)):
    """Get call outcome"""
    try:
        outcome = await db.call_outcomes.find_one({"call_id": call_id}, {"_id": 0})
        if not outcome:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call outcome not found"
            )
        return outcome
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get call outcome error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch call outcome"
        )

@router.get("/{call_id}/summary", response_model=CallSummary)
async def get_call_summary(call_id: str, user_id: str = Depends(get_current_user)):
    """Get call summary"""
    try:
        summary = await db.call_summaries.find_one({"call_id": call_id}, {"_id": 0})
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Call summary not found"
            )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get call summary error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch call summary"
        )