from fastapi import APIRouter, HTTPException, Depends, status
from models.campaign import CampaignCreate, Campaign
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.post("", response_model=Campaign)
async def create_campaign(campaign_data: CampaignCreate, user_id: str = Depends(get_current_user)):
    """Create a new campaign"""
    try:
        campaign = Campaign(
            **campaign_data.model_dump(),
            user_id=user_id
        )
        
        campaign_doc = prepare_for_mongo(campaign.model_dump())
        await db.campaigns.insert_one(campaign_doc)
        
        return campaign
    except Exception as e:
        logger.error(f"Create campaign error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create campaign"
        )

@router.get("", response_model=List[Campaign])
async def get_campaigns(user_id: str = Depends(get_current_user)):
    """Get all campaigns for the current user"""
    try:
        campaigns = await db.campaigns.find({"user_id": user_id}, {"_id": 0}).to_list(1000)
        return campaigns
    except Exception as e:
        logger.error(f"Get campaigns error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch campaigns"
        )

@router.get("/{campaign_id}", response_model=Campaign)
async def get_campaign(campaign_id: str, user_id: str = Depends(get_current_user)):
    """Get a specific campaign"""
    try:
        campaign = await db.campaigns.find_one(
            {"id": campaign_id, "user_id": user_id}, 
            {"_id": 0}
        )
        if not campaign:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Campaign not found"
            )
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get campaign error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch campaign"
        )