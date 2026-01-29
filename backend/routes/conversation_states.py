from fastapi import APIRouter, HTTPException, Depends, status
from models.call import ConversationState
from utils.security import get_current_user
from utils.db import db
from typing import List
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/conversation-states", tags=["Conversation States"])

@router.get("", response_model=List[ConversationState])
async def get_conversation_states(call_id: str = None, user_id: str = Depends(get_current_user)):
    """Get conversation states, optionally filtered by call_id"""
    try:
        query = {}
        if call_id:
            query["call_id"] = call_id
        
        states = await db.conversation_states.find(query, {"_id": 0}).to_list(1000)
        return states
    except Exception as e:
        logger.error(f"Get conversation states error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch conversation states"
        )
