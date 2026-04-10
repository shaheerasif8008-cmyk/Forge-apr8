"""Type 5: Policy changes — client-controlled business rules."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PolicyRule(BaseModel):
    """A client-defined behavioural rule applied to their employee."""

    rule_id: str
    description: str
    condition: str = Field(description="e.g. 'time_of_day > 17:00'")
    action: str = Field(description="e.g. 'suppress_non_urgent_messages'")
    priority: int = Field(2, description="1=direct command, 2=portal rule, 3=adaptive")
    active: bool = True
