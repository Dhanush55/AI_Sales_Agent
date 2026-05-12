from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime, timezone
import uuid


class ExampleConversation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    transcript: str                              # full transcribed text
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CampaignBase(BaseModel):
    name: str
    goal: str
    language: Literal["indian_english", "hindi", "kannada", "tamil", "telugu"]

    # Product information fed to the AI
    product_name: Optional[str] = None
    product_description: Optional[str] = None
    key_features: Optional[List[str]] = []
    pricing: Optional[str] = None
    target_customer: Optional[str] = None
    objection_handling: Optional[str] = None

    # Real call recordings transcribed and used as style examples
    example_conversations: Optional[List[ExampleConversation]] = []


class CampaignCreate(CampaignBase):
    pass


class Campaign(CampaignBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    status: str = "active"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
