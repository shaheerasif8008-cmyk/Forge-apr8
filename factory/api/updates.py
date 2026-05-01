"""Update management endpoints for deployed employees."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from factory.auth import FactoryAuthContext, ensure_org_access, get_factory_auth
from factory.database import get_db_session
from factory.persistence import get_deployment
from factory.updates.learning_updater import LearningUpdateState
from factory.updates.marketplace import MarketplaceModule, MarketplacePurchase
from factory.updates.module_upgrader import ModuleUpgrade
from factory.updates.policy_manager import PolicyRule, policy_manager
from factory.updates.security_updater import DEFAULT_SECURITY_UPDATES, SecurityUpdateState

router = APIRouter(prefix="/updates", tags=["updates"])

_LEARNING_STATE: dict[str, LearningUpdateState] = {}
_MODULE_UPGRADES: dict[str, list[ModuleUpgrade]] = {}
_SECURITY_STATE: dict[str, dict[str, SecurityUpdateState]] = {}
_MARKETPLACE_PURCHASES: dict[str, list[MarketplacePurchase]] = {}
_MARKETPLACE_MODULES = [
    MarketplaceModule(
        component_id="research_engine",
        name="Research Engine",
        description="Multi-source research and synthesis",
        category="work",
        price_monthly_usd=500,
    )
]
_MAX_SECURITY_DELAY = timedelta(days=30)


class LearningToggleRequest(BaseModel):
    enabled: bool


class LearningPauseRequest(BaseModel):
    paused_until: datetime | None = None
    reason: str | None = None


class SecurityDelayRequest(BaseModel):
    delayed_until: datetime
    reason: str | None = None


class DeclineModuleRequest(BaseModel):
    reason: str | None = None


class PurchaseMarketplaceModuleRequest(BaseModel):
    license_type: str = "monthly"


async def _authorize_deployment(
    deployment_id: UUID,
    auth: FactoryAuthContext,
    session,
) -> str:
    deployment = await get_deployment(session, deployment_id)
    if deployment is None:
        raise HTTPException(status_code=404, detail="deployment_not_found")
    ensure_org_access(auth, deployment.org_id)
    return str(deployment_id)


def _security_state_for(deployment_key: str) -> dict[str, SecurityUpdateState]:
    if deployment_key not in _SECURITY_STATE:
        _SECURITY_STATE[deployment_key] = {
            update.update_id: SecurityUpdateState(**update.model_dump())
            for update in DEFAULT_SECURITY_UPDATES
        }
    return _SECURITY_STATE[deployment_key]


def _get_security_update(deployment_key: str, update_id: str) -> SecurityUpdateState:
    update = _security_state_for(deployment_key).get(update_id)
    if update is None:
        raise HTTPException(status_code=404, detail="security_update_not_found")
    return update


def _get_module_upgrade(deployment_key: str, upgrade_id: str) -> ModuleUpgrade:
    for upgrade in _MODULE_UPGRADES.get(deployment_key, []):
        if upgrade.upgrade_id == upgrade_id:
            return upgrade
    raise HTTPException(status_code=404, detail="module_upgrade_not_found")


def _get_marketplace_module(component_id: str) -> MarketplaceModule:
    for module in _MARKETPLACE_MODULES:
        if module.component_id == component_id:
            return module
    raise HTTPException(status_code=404, detail="marketplace_module_not_found")


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


@router.get("/{deployment_id}")
async def get_updates(
    deployment_id: UUID,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    return {
        "security": [
            update.model_dump(mode="json") for update in _security_state_for(key).values()
        ],
        "learning": _LEARNING_STATE.get(key, LearningUpdateState()).model_dump(mode="json"),
        "module_upgrades": [update.model_dump(mode="json") for update in _MODULE_UPGRADES.get(key, [])],
        "marketplace": [module.model_dump(mode="json") for module in _MARKETPLACE_MODULES],
        "marketplace_purchases": [
            purchase.model_dump(mode="json") for purchase in _MARKETPLACE_PURCHASES.get(key, [])
        ],
        "policies": [rule.model_dump(mode="json") for rule in policy_manager.list_rules(key)],
    }


@router.put("/{deployment_id}/learning")
async def set_learning_state(
    deployment_id: UUID,
    payload: LearningToggleRequest,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    state = LearningUpdateState(enabled=payload.enabled)
    _LEARNING_STATE[key] = state
    return state.model_dump(mode="json")


@router.post("/{deployment_id}/learning/pause")
async def pause_learning(
    deployment_id: UUID,
    payload: LearningPauseRequest,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    current = _LEARNING_STATE.get(key, LearningUpdateState())
    state = current.model_copy(
        update={
            "enabled": False,
            "paused": True,
            "paused_until": payload.paused_until,
            "pause_reason": payload.reason,
        }
    )
    _LEARNING_STATE[key] = state
    return state.model_dump(mode="json")


@router.post("/{deployment_id}/learning/resume")
async def resume_learning(
    deployment_id: UUID,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    current = _LEARNING_STATE.get(key, LearningUpdateState())
    state = current.model_copy(
        update={
            "enabled": True,
            "paused": False,
            "paused_until": None,
            "pause_reason": None,
        }
    )
    _LEARNING_STATE[key] = state
    return state.model_dump(mode="json")


@router.post("/{deployment_id}/modules")
async def schedule_module_upgrade(
    deployment_id: UUID,
    payload: ModuleUpgrade,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    payload.status = "scheduled"
    _MODULE_UPGRADES.setdefault(key, []).append(payload)
    return payload.model_dump(mode="json")


@router.post("/{deployment_id}/modules/{upgrade_id}/preview")
async def preview_module_upgrade(
    deployment_id: UUID,
    upgrade_id: str,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    upgrade = _get_module_upgrade(key, upgrade_id)
    upgrade.status = "previewed"
    upgrade.previewed_at = datetime.now(UTC)
    return upgrade.model_dump(mode="json")


@router.post("/{deployment_id}/modules/{upgrade_id}/install")
async def install_module_upgrade(
    deployment_id: UUID,
    upgrade_id: str,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    upgrade = _get_module_upgrade(key, upgrade_id)
    upgrade.status = "installed"
    upgrade.installed_at = datetime.now(UTC)
    return upgrade.model_dump(mode="json")


@router.post("/{deployment_id}/modules/{upgrade_id}/decline")
async def decline_module_upgrade(
    deployment_id: UUID,
    upgrade_id: str,
    payload: DeclineModuleRequest,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    upgrade = _get_module_upgrade(key, upgrade_id)
    upgrade.status = "declined"
    upgrade.declined_at = datetime.now(UTC)
    upgrade.decline_reason = payload.reason
    return upgrade.model_dump(mode="json")


@router.get("/{deployment_id}/marketplace")
async def list_marketplace_modules(
    deployment_id: UUID,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> list[dict]:
    await _authorize_deployment(deployment_id, auth, session)
    return [module.model_dump(mode="json") for module in _MARKETPLACE_MODULES]


@router.post("/{deployment_id}/marketplace/{component_id}/purchase")
async def purchase_marketplace_module(
    deployment_id: UUID,
    component_id: str,
    payload: PurchaseMarketplaceModuleRequest,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    _get_marketplace_module(component_id)
    if payload.license_type not in {"one_time", "monthly"}:
        raise HTTPException(status_code=422, detail="invalid_license_type")
    purchase = MarketplacePurchase(component_id=component_id, license_type=payload.license_type)
    _MARKETPLACE_PURCHASES.setdefault(key, []).append(purchase)
    return purchase.model_dump(mode="json")


@router.post("/{deployment_id}/security/{update_id}/apply")
async def apply_security_update(
    deployment_id: UUID,
    update_id: str,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    update = _get_security_update(key, update_id)
    update.status = "applied"
    update.applied_at = datetime.now(UTC)
    update.delayed_until = None
    update.delay_reason = None
    return update.model_dump(mode="json")


@router.post("/{deployment_id}/security/{update_id}/delay")
async def delay_security_update(
    deployment_id: UUID,
    update_id: str,
    payload: SecurityDelayRequest,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    update = _get_security_update(key, update_id)
    now = datetime.now(UTC)
    delayed_until = _as_utc(payload.delayed_until)
    if delayed_until > now + _MAX_SECURITY_DELAY:
        raise HTTPException(status_code=422, detail="security_delay_exceeds_30_days")
    update.status = "delayed"
    update.delayed_until = delayed_until
    update.delay_reason = payload.reason
    return update.model_dump(mode="json")


@router.post("/{deployment_id}/security/{update_id}/rollback")
async def rollback_security_update(
    deployment_id: UUID,
    update_id: str,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    update = _get_security_update(key, update_id)
    if not update.rollbackable:
        raise HTTPException(status_code=409, detail="security_update_not_rollbackable")
    update.status = "rolled_back"
    update.rolled_back_at = datetime.now(UTC)
    return update.model_dump(mode="json")


@router.get("/{deployment_id}/policies")
async def list_policy_rules(
    deployment_id: UUID,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> list[dict]:
    key = await _authorize_deployment(deployment_id, auth, session)
    return [rule.model_dump(mode="json") for rule in policy_manager.list_rules(key)]


@router.post("/{deployment_id}/policies")
async def add_policy_rule(
    deployment_id: UUID,
    payload: PolicyRule,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    rule = policy_manager.add_rule(key, payload)
    return rule.model_dump(mode="json")


@router.post("/{deployment_id}/policies/{rule_id}/deactivate")
async def deactivate_policy_rule(
    deployment_id: UUID,
    rule_id: str,
    auth: FactoryAuthContext = Depends(get_factory_auth),
    session=Depends(get_db_session),
) -> dict:
    key = await _authorize_deployment(deployment_id, auth, session)
    rule = policy_manager.deactivate_rule(key, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="policy_rule_not_found")
    return rule.model_dump(mode="json")
