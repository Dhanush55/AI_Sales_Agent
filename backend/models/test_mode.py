from pydantic import BaseModel
from typing import Literal, Optional

class TestModeInput(BaseModel):
    campaign_id: str
    user_input: str
    call_id: Optional[str] = None
    simulate: Optional[Literal["silence", "interruption"]] = None

class TestModeResponse(BaseModel):
    call_id: str
    agent_response: str
    should_end_call: bool
    conversation_state: dict