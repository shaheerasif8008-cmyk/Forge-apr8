"""Client and organisation data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, EmailStr, Field


class SubscriptionTier(str, Enum):
    ENTERPRISE = "enterprise"
    PRO = "pro"


class ClientOrg(BaseModel):
    """A Forge client organisation."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    slug: str
    industry: str = ""
    tier: SubscriptionTier = SubscriptionTier.ENTERPRISE
    contact_email: EmailStr
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Client(BaseModel):
    """An individual user within a ClientOrg."""

    id: UUID = Field(default_factory=uuid4)
    org_id: UUID
    email: EmailStr
    name: str
    role: str = "owner"
    created_at: datetime = Field(default_factory=datetime.utcnow)
