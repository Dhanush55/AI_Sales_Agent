from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone
import uuid

class CampaignBase(BaseModel):
    name: str
    goal: str
    language: Literal["indian_english", "hindi", "kannada", "tamil"]
    
class CampaignCreate(CampaignBase):
    pass

class Campaign(CampaignBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))