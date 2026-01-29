from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid

class LeadBase(BaseModel):
    name: str
    phone: str

class LeadCreate(LeadBase):
    campaign_id: str

class Lead(LeadBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    campaign_id: str
    status: Literal["pending", "contacted", "interested", "not_interested", "callback"] = "pending"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))