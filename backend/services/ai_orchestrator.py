from openai import AsyncOpenAI
from config import settings
from models.call import ConversationState, ConversationTurn
from typing import Tuple, List, Dict, AsyncGenerator
import logging
import os
import re

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """Core AI service for voice agent conversation logic"""

    def __init__(self):
        if settings.GROQ_API_KEY:
            self.client = AsyncOpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
            )
            self.model = "llama-3.3-70b-versatile"
            logger.info("Using Groq (llama-3.3-70b) as LLM provider")
        else:
            api_key = settings.OPENAI_API_KEY or settings.EMERGENT_LLM_KEY or ""
            base_url = settings.OPENAI_BASE_URL if settings.OPENAI_BASE_URL else None
            self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            self.model = "gpt-4o"
            logger.info("Using OpenAI (gpt-4o) as LLM provider")

    def _get_system_prompt(self, campaign_goal: str, language: str, campaign: dict = None) -> str:
        language_map = {
            "indian_english": "Indian English",
            "hindi": "Hindi",
            "kannada": "Kannada",
            "tamil": "Tamil",
            "telugu": "Telugu",
        }
        lang_name = language_map.get(language, "Indian English")

        # Language-specific dialect instructions
        dialect_guide = {
            "kannada": """
BANGALORE KANGLISH STYLE:
- You speak Bangalore-style Kanglish: natural mix of Kannada + English, exactly how locals talk
- Use these naturally (don't overdo it): "swalpa" (a little), "gottilla" (don't know), "banni" (come/okay), "howdu" (yes/correct), "illa" (no), "enu" (what), "bega" (fast/quickly), "ayta" (done/okay), "machha" (friend/man), "boss" (address term), "adjust maadi" (please adjust)
- Typical sentence pattern: English frame + Kannada fillers — "Sir, swalpa time iddira? One minute only."
- Acknowledgements: "Howdu howdu", "Ayta sir", "Sari sari", "Okay maadi"
- Natural filler: "basically", "actually", "only" at end of sentences ("Good product only sir")
- Never sound formal or robotic — sound like a friendly local Bengaluru person
- Example: "Namaskara sir! Neevu Bangalore-alli idhira? We have one good offer, swalpa keḷi." """,
            "hindi": """
HINGLISH STYLE (Delhi/Mumbai flavour):
- Mix Hindi and English naturally as urban Indians speak
- Use: "haan ji", "bilkul", "theek hai", "kya baat hai", "suno", "bhai", "yaar", "bas"
- Sentence pattern: Hindi frame + English terms — "Sir, ye product bahut useful hai, basically..."
- Acknowledgements: "Haan haan", "Theek hai ji", "Bilkul sahi"
- Sound like a friendly, warm, real person — not a call center script """,
            "tamil": """
TAMIL STYLE (Chennai/Bangalore Tamil):
- Natural code-switching between Tamil and English
- Use: "sari", "aamaa", "illai", "nalla", "paakalam", "sollungal", "romba", "konjam"
- Sound like a helpful local — warm, respectful, not scripted """,
            "telugu": """
TELUGU STYLE (Hyderabad/Bangalore Telugu):
- Natural Telegu-English mix as Hyderabadis speak
- Use: "avunu", "ledu", "cheppandi", "bagundi", "konjam", "emi", "okay na"
- Hyderabadi flavour: "enti", "chusko", "correct ga" """,
        }
        dialect_section = dialect_guide.get(language, "")

        # Build product knowledge section
        product_section = ""
        if campaign:
            parts = []
            if campaign.get("product_name"):
                parts.append(f"Product: {campaign['product_name']}")
            if campaign.get("product_description"):
                parts.append(f"Description: {campaign['product_description']}")
            if campaign.get("key_features"):
                features = "\n  - ".join(campaign["key_features"])
                parts.append(f"Key Features:\n  - {features}")
            if campaign.get("pricing"):
                parts.append(f"Pricing: {campaign['pricing']}")
            if campaign.get("target_customer"):
                parts.append(f"Target Customer: {campaign['target_customer']}")
            if campaign.get("objection_handling"):
                parts.append(f"Objection Handling: {campaign['objection_handling']}")
            if parts:
                product_section = "\n\nPRODUCT KNOWLEDGE:\n" + "\n".join(parts)

        # Build example conversations section
        example_section = ""
        if campaign:
            examples = campaign.get("example_conversations", [])
            if examples:
                example_texts = []
                for i, ex in enumerate(examples[:3], 1):  # max 3 examples to stay within token limit
                    example_texts.append(f"Example {i} (from recording '{ex.get('filename', 'unknown')}'):\n{ex.get('transcript', '')}")
                example_section = "\n\nEXAMPLE SUCCESSFUL CONVERSATIONS (study and mimic this sales style, tone, and approach):\n" + "\n\n".join(example_texts)

        return f"""You are a professional sales agent. Your goal is: {campaign_goal}{product_section}{example_section}{dialect_section}

CONVERSATIONAL STYLE (VOICE-FIRST):
- You are having a natural voice conversation with a human
- Keep ALL responses extremely brief: 1 sentence preferred, max 2 sentences
- Use short acknowledgements in {lang_name} style
- Sound natural and human-like when spoken aloud
- Speak in {lang_name} throughout the conversation — use the dialect style above
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

ENDING THE CALL:
When ending, include "[END_CALL]" in your final response.
Examples:
- "Got it. I'll call back later. [END_CALL]"
- "Understood. Thank you. [END_CALL]"
- "No problem. Have a great day! [END_CALL]"

Be natural, brief, and respectful. Quality over quantity."""

    def _build_messages(self, campaign_goal: str, language: str,
                        conversation_state: ConversationState,
                        user_input: str, campaign: dict = None) -> List[Dict]:
        """Build OpenAI messages array from conversation history"""
        messages = [
            {"role": "system", "content": self._get_system_prompt(campaign_goal, language, campaign)}
        ]

        # Add conversation history
        for turn in conversation_state.turns:
            if turn.speaker == "user":
                messages.append({"role": "user", "content": turn.text})
            elif turn.speaker == "agent":
                messages.append({"role": "assistant", "content": turn.text})

        # Add context note + current input
        context = self._build_context_summary(conversation_state)
        full_input = f"{context}\n{user_input}" if context.strip() else user_input
        messages.append({"role": "user", "content": full_input})

        return messages

    async def process_turn(self,
                           user_input: str,
                           campaign_goal: str,
                           language: str,
                           conversation_state: ConversationState,
                           campaign: dict = None) -> Tuple[str, bool]:
        try:
            # Auto-detect language from first user input
            if not conversation_state.language_detected and conversation_state.current_turn == 0:
                detected = self._detect_language(user_input)
                if detected:
                    conversation_state.language_detected = detected
                    language = detected
            elif conversation_state.language_detected:
                language = conversation_state.language_detected

            # Check for stopping triggers in user input
            user_lower = user_input.lower()
            if "busy" in user_lower or "not now" in user_lower:
                conversation_state.context["user_is_busy"] = True
            if "not interested" in user_lower or "no thanks" in user_lower:
                conversation_state.not_interested_count += 1
            if "[User is silent]" in user_input or user_input.strip() == "":
                conversation_state.context["silence_count"] = (
                    conversation_state.context.get("silence_count", 0) + 1
                )

            messages = self._build_messages(campaign_goal, language,
                                            conversation_state, user_input, campaign)

            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
                temperature=0.7,
            )
            response = completion.choices[0].message.content or ""

            should_end = self._should_end_call(response, conversation_state, user_input)
            clean_response = response.replace("[END_CALL]", "").strip()

            # Update state
            conversation_state.current_turn += 1
            conversation_state.turns.append(ConversationTurn(speaker="user", text=user_input))
            conversation_state.turns.append(ConversationTurn(speaker="agent", text=clean_response))

            return clean_response, should_end

        except Exception as e:
            logger.error(f"Error in AI orchestrator: {str(e)}")
            return "I apologize, I'm experiencing technical difficulties. Can we try again?", False

    async def stream_turn(self,
                          user_input: str,
                          campaign_goal: str,
                          language: str,
                          conversation_state: ConversationState,
                          campaign: dict = None) -> AsyncGenerator[Dict, None]:
        """Stream LLM response token-by-token, yielding sentence chunks as they complete.

        Yields events:
          {"type": "delta", "text": "..."}     — incremental token text
          {"type": "sentence", "text": "..."}  — complete sentence ready for TTS
          {"type": "final", "text": full, "should_end_call": bool}  — end of stream
        """
        try:
            # Same pre-processing as process_turn
            if not conversation_state.language_detected and conversation_state.current_turn == 0:
                detected = self._detect_language(user_input)
                if detected:
                    conversation_state.language_detected = detected
                    language = detected
            elif conversation_state.language_detected:
                language = conversation_state.language_detected

            user_lower = user_input.lower()
            if "busy" in user_lower or "not now" in user_lower:
                conversation_state.context["user_is_busy"] = True
            if "not interested" in user_lower or "no thanks" in user_lower:
                conversation_state.not_interested_count += 1
            if "[User is silent]" in user_input or user_input.strip() == "":
                conversation_state.context["silence_count"] = (
                    conversation_state.context.get("silence_count", 0) + 1
                )

            messages = self._build_messages(campaign_goal, language,
                                            conversation_state, user_input, campaign)

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                stream=True,
            )

            full_response = ""
            buffer = ""
            sentence_re = re.compile(r"(.+?[.!?।]+)(\s|$)")

            async for chunk in stream:
                delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
                if not delta:
                    continue
                full_response += delta
                buffer += delta
                yield {"type": "delta", "text": delta}

                # Flush every complete sentence to TTS as soon as we hit a boundary
                while True:
                    m = sentence_re.match(buffer)
                    if not m:
                        break
                    sentence = m.group(1).strip()
                    buffer = buffer[m.end():]
                    cleaned = sentence.replace("[END_CALL]", "").strip()
                    if cleaned:
                        yield {"type": "sentence", "text": cleaned}

            # Flush any tail (no terminal punctuation)
            tail = buffer.strip().replace("[END_CALL]", "").strip()
            if tail:
                yield {"type": "sentence", "text": tail}

            should_end = self._should_end_call(full_response, conversation_state, user_input)
            clean_response = full_response.replace("[END_CALL]", "").strip()

            conversation_state.current_turn += 1
            conversation_state.turns.append(ConversationTurn(speaker="user", text=user_input))
            conversation_state.turns.append(ConversationTurn(speaker="agent", text=clean_response))

            yield {
                "type": "final",
                "text": clean_response,
                "should_end_call": should_end,
                "language": conversation_state.language_detected or language,
            }

        except Exception as e:
            logger.error(f"Error in streaming AI orchestrator: {e}")
            yield {
                "type": "final",
                "text": "I apologize, I'm experiencing technical difficulties.",
                "should_end_call": False,
                "language": language,
                "error": str(e),
            }

    def _build_context_summary(self, state: ConversationState) -> str:
        if state.current_turn == 0:
            return ""
        parts = [f"Turn {state.current_turn}."]
        if state.not_interested_count > 0:
            parts.append(f"User said not interested {state.not_interested_count} time(s).")
        if state.context.get("user_is_busy"):
            parts.append("User is busy.")
        silence = state.context.get("silence_count", 0)
        if silence > 0:
            parts.append(f"User has been silent {silence} time(s).")
        if state.current_turn > 5:
            parts.append("Extended conversation — user appears engaged.")
        return " ".join(parts)

    def _should_end_call(self, response: str, state: ConversationState, user_input: str) -> bool:
        if "[END_CALL]" in response:
            return True
        if state.not_interested_count >= 1:
            return True
        if state.context.get("user_is_busy"):
            return True
        if state.context.get("silence_count", 0) >= 2:
            return True
        if state.current_turn >= 20:
            return True
        return False

    def _detect_language(self, user_input: str) -> str:
        # Unicode script detection — reliable for native script input from Whisper
        for ch in user_input:
            cp = ord(ch)
            if 0x0C80 <= cp <= 0x0CFF:
                return "kannada"
            if 0x0C00 <= cp <= 0x0C7F:
                return "telugu"
            if 0x0B80 <= cp <= 0x0BFF:
                return "tamil"
            if 0x0900 <= cp <= 0x097F:
                return "hindi"

        # Romanised fallback — common transliterated words
        user_lower = user_input.lower()
        kannada_kw = ["howdu", "illa", "enu", "sari", "namaskara", "beda", "aayta", "swalpа"]
        if any(k in user_lower for k in kannada_kw):
            return "kannada"
        telugu_kw = ["avunu", "kadu", "emi", "namaskaaram", "meeru", "nenu", "cheppandi", "ledu"]
        if any(k in user_lower for k in telugu_kw):
            return "telugu"
        tamil_kw = ["aam", "illai", "enna", "vanakkam", "sollungal", "paakalam", "romba"]
        if any(k in user_lower for k in tamil_kw):
            return "tamil"
        hindi_kw = ["haan", "nahi", "kya", "theek", "achha", "namaste", "kaise", "bataiye", "chaliye"]
        if any(k in user_lower for k in hindi_kw):
            return "hindi"
        return None

    async def generate_call_summary(self, conversation_state: ConversationState) -> str:
        try:
            transcript = "\n".join(
                f"{t.speaker.upper()}: {t.text}" for t in conversation_state.turns
            )
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a call summarizer. Provide a brief, professional summary in 2-3 sentences."},
                    {"role": "user", "content": f"Summarize this sales call:\n{transcript}"},
                ],
                max_tokens=150,
            )
            return completion.choices[0].message.content or "Call completed."
        except Exception as e:
            logger.error(f"Error generating summary: {str(e)}")
            return "Call completed. Unable to generate summary."


ai_orchestrator = AIOrchestrator()
