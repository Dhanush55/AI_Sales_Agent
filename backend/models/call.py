from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime, timezone
import uuid

class CallBase(BaseModel):
    lead_id: str
    campaign_id: str

class CallCreate(CallBase):
    pass

class Call(CallBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: Literal["in_progress", "completed", "failed"] = "in_progress"
    duration: Optional[int] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None

class ConversationTurn(BaseModel):
    speaker: Literal["user", "agent"]
    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ConversationState(BaseModel):
    call_id: str
    current_turn: int = 0
    questions_asked: int = 0
    is_permission_granted: bool = False
    not_interested_count: int = 0
    language_detected: Optional[str] = None
    context: dict = Field(default_factory=dict)
    turns: List[ConversationTurn] = Field(default_factory=list)

class CallOutcome(BaseModel):
    call_id: str
    outcome: Literal["interested", "not_interested", "busy", "callback_scheduled", "no_answer"]
    is_qualified: bool = False
    callback_time: Optional[datetime] = None
    notes: str = ""

class CallSummary(BaseModel):
    call_id: str
    summary_text: str
    key_points: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))