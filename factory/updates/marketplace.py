"""Type 4: Marketplace — new skill modules clients can purchase."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MarketplaceModule(BaseModel):
    component_id: str
    name: str
    description: str
    category: str
    price_one_time_usd: float | None = None
    price_monthly_usd: float | None = None
    tags: list[str] = Field(default_factory=list)
