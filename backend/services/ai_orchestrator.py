from emergentintegrations.llm.chat import LlmChat, UserMessage
from config import settings
from models.call import ConversationState, ConversationTurn
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

class AIOrchestrator:
    """Core AI service for voice agent conversation logic"""
    
    def __init__(self):
        self.api_key = settings.EMERGENT_LLM_KEY
    
    def _get_system_prompt(self, campaign_goal: str, language: str, industry: str = "B2B automotive workshop machinery") -> str:
        """Generate system prompt based on campaign context"""
        
        language_map = {
            "indian_english": "Indian English",
            "hindi": "Hindi",
            "kannada": "Kannada",
            "tamil": "Tamil"
        }
        
        lang_name = language_map.get(language, "Indian English")
        
        return f"""You are a professional B2B sales conversational agent for {industry} sales. Your goal is: {campaign_goal}

CONVERSATIONAL STYLE (VOICE-FIRST):
- You are having a natural voice conversation with a human
- Keep ALL responses extremely brief: 1 sentence preferred, max 2 sentences
- Use short acknowledgements: "Okay", "Got it", "Understood", "I see"
- Sound natural and human-like when spoken aloud
- Speak in {lang_name} throughout the conversation
- Use culturally appropriate tone for Indian business communication

CONVERSATION FLOW:
- Ask only ONE question at a time
- After EVERY user response, reassess whether to continue or stop
- Continue only if the user appears engaged and responsive
- If user hesitates, shows resistance, or slows down, reduce questioning
- Ask permission before pitching products
- Focus on qualification, not aggressive selling
- Never argue or over-explain

MANDATORY STOPPING RULES:
1. If user says "busy" or "not now": Immediately offer callback and end with [END_CALL]
2. If user says "not interested" ONCE: Acknowledge politely and end with [END_CALL]
3. If user is silent or unresponsive: Prompt once gently, then end with [END_CALL]
4. If conversation goal is achieved: End naturally with [END_CALL]
5. Never pressure or push after resistance

INTERRUPTION HANDLING:
- If user interrupts you, STOP immediately
- Respond to their interruption directly
- Do not continue your previous thought

ENDING THE CALL:
When ending (user busy, not interested, silent, or goal achieved), include "[END_CALL]" in your final response.

Examples:
- "Got it. I'll call back later. [END_CALL]"
- "Understood. Thank you. [END_CALL]"
- "No problem. Have a great day! [END_CALL]"

Be natural, brief, and respectful. Quality over quantity."""
    
    async def process_turn(self, 
                          user_input: str, 
                          campaign_goal: str, 
                          language: str,
                          conversation_state: ConversationState) -> Tuple[str, bool]:
        """
        Process a conversation turn and return agent response
        
        Returns:
            Tuple[str, bool]: (agent_response, should_end_call)
        """
        try:
            # Create new chat instance for this call if needed
            session_id = f"call_{conversation_state.call_id}"
            
            chat = LlmChat(
                api_key=self.api_key,
                session_id=session_id,
                system_message=self._get_system_prompt(campaign_goal, language)
            )
            
            # Use OpenAI GPT-4o
            chat.with_model("openai", "gpt-4o")
            
            # Build context from previous turns
            context_summary = self._build_context_summary(conversation_state)
            
            # Check for business rules
            if "busy" in user_input.lower() or "not now" in user_input.lower():
                conversation_state.context["user_is_busy"] = True
            
            if "not interested" in user_input.lower() or "no thanks" in user_input.lower():
                conversation_state.not_interested_count += 1
            
            # Prepare user message with context
            full_message = f"{context_summary}\nUser: {user_input}"
            user_message = UserMessage(text=full_message)
            
            # Get AI response
            response = await chat.send_message(user_message)
            
            # Check if call should end
            should_end = self._should_end_call(response, conversation_state)
            
            # Remove [END_CALL] marker from response if present
            clean_response = response.replace("[END_CALL]", "").strip()
            
            # Update conversation state
            conversation_state.current_turn += 1
            conversation_state.turns.append(ConversationTurn(speaker="user", text=user_input))
            conversation_state.turns.append(ConversationTurn(speaker="agent", text=clean_response))
            
            # Count questions asked
            if "?" in clean_response:
                conversation_state.questions_asked += 1
            
            return clean_response, should_end
            
        except Exception as e:
            logger.error(f"Error in AI orchestrator: {str(e)}")
            return "I apologize, I'm experiencing technical difficulties. Can we try again?", False
    
    def _build_context_summary(self, state: ConversationState) -> str:
        """Build context summary from conversation state"""
        summary = f"Turn {state.current_turn}. Questions asked: {state.questions_asked}/3."
        
        if state.not_interested_count > 0:
            summary += f" User has said not interested {state.not_interested_count} time(s)."
        
        if state.context.get("user_is_busy"):
            summary += " User indicated they are busy."
        
        return summary
    
    def _should_end_call(self, response: str, state: ConversationState) -> bool:
        """Determine if call should end based on response and state"""
        # Check for end marker
        if "[END_CALL]" in response:
            return True
        
        # Business rules
        if state.not_interested_count >= 2:
            return True
        
        if state.context.get("user_is_busy"):
            return True
        
        if state.questions_asked >= 3:
            return True
        
        if state.current_turn >= 15:
            return True
        
        return False
    
    async def generate_call_summary(self, conversation_state: ConversationState) -> str:
        """Generate a summary of the call"""
        try:
            chat = LlmChat(
                api_key=self.api_key,
                session_id=f"summary_{conversation_state.call_id}",
                system_message="You are a call summarizer. Provide a brief, professional summary of the call in 2-3 sentences."
            )
            
            chat.with_model("openai", "gpt-4o")
            
            # Build conversation transcript
            transcript = "\n".join([
                f"{turn.speaker.upper()}: {turn.text}" 
                for turn in conversation_state.turns
            ])
            
            user_message = UserMessage(text=f"Summarize this sales call:\n{transcript}")
            summary = await chat.send_message(user_message)
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Call completed. Unable to generate summary."

ai_orchestrator = AIOrchestrator()