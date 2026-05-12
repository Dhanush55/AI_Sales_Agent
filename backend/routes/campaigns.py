from fastapi import APIRouter, HTTPException, Depends, status, UploadFile, File
from models.campaign import CampaignCreate, Campaign, ExampleConversation
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from services.voice_service import voice_service
from typing import List
import io
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


@router.patch("/{campaign_id}")
async def update_campaign(campaign_id: str, updates: dict, user_id: str = Depends(get_current_user)):
    """Update campaign fields (name, goal, language, product info, etc.)"""
    try:
        campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        # Disallow changing protected fields
        updates.pop("id", None)
        updates.pop("user_id", None)
        updates.pop("created_at", None)
        await db.campaigns.update_one({"id": campaign_id}, {"$set": updates})
        updated = await db.campaigns.find_one({"id": campaign_id}, {"_id": 0})
        return updated
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update campaign error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update campaign")


@router.post("/{campaign_id}/example-conversations")
async def upload_example_conversation(
    campaign_id: str,
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """Upload an audio recording, transcribe it, and store as an example conversation."""
    try:
        campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")

        audio_bytes = await file.read()
        if len(audio_bytes) == 0:
            raise HTTPException(status_code=400, detail="Empty file")

        # Transcribe using faster-whisper
        language = campaign.get("language", "indian_english")
        transcript = await voice_service.speech_to_text(io.BytesIO(audio_bytes), language)
        if not transcript or not transcript.strip():
            raise HTTPException(status_code=422, detail="Could not transcribe audio — try a clearer recording")

        example = ExampleConversation(filename=file.filename or "recording", transcript=transcript.strip())
        example_doc = prepare_for_mongo(example.model_dump())

        await db.campaigns.update_one(
            {"id": campaign_id},
            {"$push": {"example_conversations": example_doc}}
        )
        return {"message": "Uploaded and transcribed successfully", "example": example_doc}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload example conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to process recording")


@router.delete("/{campaign_id}/example-conversations/{example_id}")
async def delete_example_conversation(
    campaign_id: str,
    example_id: str,
    user_id: str = Depends(get_current_user),
):
    """Remove an example conversation from a campaign."""
    try:
        campaign = await db.campaigns.find_one({"id": campaign_id, "user_id": user_id})
        if not campaign:
            raise HTTPException(status_code=404, detail="Campaign not found")
        await db.campaigns.update_one(
            {"id": campaign_id},
            {"$pull": {"example_conversations": {"id": example_id}}}
        )
        return {"message": "Deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete example conversation error: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete")