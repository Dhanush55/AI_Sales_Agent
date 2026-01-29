from fastapi import APIRouter, HTTPException, Depends, status
from models.lead import LeadCreate, Lead
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/leads", tags=["Leads"])

@router.post("", response_model=Lead)
async def create_lead(lead_data: LeadCreate, user_id: str = Depends(get_current_user)):
    """Create a new lead"""
    try:
        # Verify campaign belongs to user
        campaign = await db.campaigns.find_one(
            {"id": lead_data.campaign_id, "user_id": user_id}
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        
        lead = Lead(**lead_data.model_dump())
        lead_doc = prepare_for_mongo(lead.model_dump())
        await db.leads.insert_one(lead_doc)
        
        return lead
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create lead error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create lead"
        )

@router.get("", response_model=List[Lead])
async def get_leads(campaign_id: str = None, user_id: str = Depends(get_current_user)):
    """Get leads, optionally filtered by campaign"""
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
        
        leads = await db.leads.find(query, {"_id": 0}).to_list(1000)
        return leads
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get leads error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch leads"
        )