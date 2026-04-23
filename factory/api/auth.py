"""Token issuance for the factory API."""

from __future__ import annotations

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from factory.auth import create_factory_token
from factory.config import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["auth"])


class TokenRequest(BaseModel):
    api_key: str
    subject: str = "factory-operator"
    org_ids: list[UUID] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=lambda: ["factory:admin"])


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


@router.post("/auth/token", response_model=TokenResponse, summary="Exchange API key for JWT")
async def issue_token(body: TokenRequest) -> TokenResponse:
    """Issue a short-lived JWT in exchange for the factory API key."""
    settings = get_settings()
    if body.api_key != settings.factory_jwt_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    token = create_factory_token(
        subject=body.subject,
        org_ids=body.org_ids,
        roles=body.roles,
    )
    logger.info("factory_token_issued", sub=body.subject)
    return TokenResponse(access_token=token, expires_in_minutes=settings.jwt_expiration_minutes)
