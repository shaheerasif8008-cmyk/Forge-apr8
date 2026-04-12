"""Type 3: Skill module upgrades — optional, client previews and installs."""

from __future__ import annotations

from pydantic import BaseModel


class ModuleUpgrade(BaseModel):
    component_id: str
    target_version: str
    summary: str
