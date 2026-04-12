"""Update management endpoints for deployed employees."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from factory.updates.learning_updater import LearningUpdateState
from factory.updates.marketplace import MarketplaceModule
from factory.updates.module_upgrader import ModuleUpgrade
from factory.updates.policy_manager import PolicyRule, policy_manager
from factory.updates.security_updater import DEFAULT_SECURITY_UPDATES

router = APIRouter(prefix="/updates", tags=["updates"])

_LEARNING_STATE: dict[str, LearningUpdateState] = {}
_MODULE_UPGRADES: dict[str, list[ModuleUpgrade]] = {}


class LearningToggleRequest(BaseModel):
    enabled: bool


@router.get("/{deployment_id}")
async def get_updates(deployment_id: UUID) -> dict:
    key = str(deployment_id)
    return {
        "security": [update.model_dump(mode="json") for update in DEFAULT_SECURITY_UPDATES],
        "learning": _LEARNING_STATE.get(key, LearningUpdateState()).model_dump(mode="json"),
        "module_upgrades": [update.model_dump(mode="json") for update in _MODULE_UPGRADES.get(key, [])],
        "marketplace": [
            MarketplaceModule(
                component_id="research_engine",
                name="Research Engine",
                description="Multi-source research and synthesis",
                category="work",
                price_monthly_usd=500,
            ).model_dump(mode="json")
        ],
        "policies": [rule.model_dump(mode="json") for rule in policy_manager.list_rules(key)],
    }


@router.put("/{deployment_id}/learning")
async def set_learning_state(deployment_id: UUID, payload: LearningToggleRequest) -> dict:
    state = LearningUpdateState(enabled=payload.enabled)
    _LEARNING_STATE[str(deployment_id)] = state
    return state.model_dump(mode="json")


@router.post("/{deployment_id}/modules")
async def schedule_module_upgrade(deployment_id: UUID, payload: ModuleUpgrade) -> dict:
    _MODULE_UPGRADES.setdefault(str(deployment_id), []).append(payload)
    return payload.model_dump(mode="json")


@router.post("/{deployment_id}/policies")
async def add_policy_rule(deployment_id: UUID, payload: PolicyRule) -> dict:
    rule = policy_manager.add_rule(str(deployment_id), payload)
    return rule.model_dump(mode="json")
