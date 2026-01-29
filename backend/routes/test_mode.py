from fastapi import APIRouter, HTTPException, Depends, status
from models.test_mode import TestModeInput, TestModeResponse
from models.call import Call, ConversationState, CallOutcome, CallSummary
from utils.security import get_current_user
from utils.db import db, prepare_for_mongo
from services.ai_orchestrator import ai_orchestrator
from datetime import datetime, timezone
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
            conversation_state=conversation_state
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
            outcome = self._determine_outcome(conversation_state)
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

def _determine_outcome(state: ConversationState) -> CallOutcome:
    """Determine call outcome from conversation state"""
    if state.not_interested_count >= 2:
        outcome_type = "not_interested"
        is_qualified = False
    elif state.context.get("user_is_busy"):
        outcome_type = "busy"
        is_qualified = False
    elif state.questions_asked >= 3:
        outcome_type = "interested"
        is_qualified = True
    else:
        outcome_type = "callback_scheduled"
        is_qualified = False
    
    return CallOutcome(
        call_id=state.call_id,
        outcome=outcome_type,
        is_qualified=is_qualified,
        notes=f"Conversation completed after {state.current_turn} turns"
    )