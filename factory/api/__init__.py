"""Factory API router — aggregates all v1 sub-routers."""

from fastapi import APIRouter, Depends

from factory.api.analyst import router as analyst_router
from factory.api.auth import router as auth_router
from factory.api.builds import router as builds_router
from factory.api.commissions import router as commissions_router
from factory.api.deployments import router as deployments_router
from factory.api.health import router as health_router
from factory.api.monitoring import router as monitoring_router
from factory.api.roster import router as roster_router
from factory.api.updates import router as updates_router
from factory.auth import require_factory_auth

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(analyst_router, dependencies=[Depends(require_factory_auth)])
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(commissions_router, dependencies=[Depends(require_factory_auth)])
api_router.include_router(builds_router, dependencies=[Depends(require_factory_auth)])
api_router.include_router(deployments_router, dependencies=[Depends(require_factory_auth)])
api_router.include_router(monitoring_router, dependencies=[Depends(require_factory_auth)])
api_router.include_router(roster_router, dependencies=[Depends(require_factory_auth)])
api_router.include_router(updates_router, dependencies=[Depends(require_factory_auth)])
