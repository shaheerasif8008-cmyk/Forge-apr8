"""Type 4: Marketplace — new skill modules clients can purchase."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class MarketplaceModule(BaseModel):
    component_id: str
    name: str
    description: str
    category: str
    price_one_time_usd: float | None = None
    price_monthly_usd: float | None = None
    tags: list[str] = Field(default_factory=list)


class MarketplacePurchase(BaseModel):
    purchase_id: str = Field(default_factory=lambda: str(uuid4()))
    component_id: str
    license_type: Literal["one_time", "monthly"]
    status: Literal["purchased"] = "purchased"
    purchased_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
