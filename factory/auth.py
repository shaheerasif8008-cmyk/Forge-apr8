"""Authentication and tenant-authorization helpers for the factory API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, status
from jwt import PyJWKClient

from factory.config import get_settings


@dataclass(slots=True)
class FactoryAuthContext:
    subject: str
    org_ids: set[str]
    roles: set[str]
    claims: dict[str, Any]
    scheme: str


def create_factory_token(
    *,
    subject: str,
    org_ids: list[str] | list[UUID],
    roles: list[str] | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "org_ids": [str(org_id) for org_id in org_ids],
        "roles": list(roles or ["factory:admin"]),
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
        **(extra_claims or {}),
    }
    return jwt.encode(payload, settings.factory_jwt_secret, algorithm=settings.jwt_algorithm)


async def require_factory_auth(request: Request) -> FactoryAuthContext:
    settings = get_settings()
    auth_header = request.headers.get("authorization", "").strip()
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")

    try:
        if settings.clerk_jwks_url:
            claims = _decode_clerk_token(token)
            scheme = "clerk"
        else:
            claims = jwt.decode(
                token,
                settings.factory_jwt_secret,
                algorithms=[settings.jwt_algorithm],
                audience=settings.factory_jwt_audience or None,
                issuer=settings.factory_jwt_issuer or None,
                options={"verify_aud": bool(settings.factory_jwt_audience)},
            )
            scheme = "shared_secret"
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc

    subject = str(claims.get("sub", "")).strip()
    org_ids = {
        str(org_id)
        for org_id in (claims.get("org_ids") or _coerce_org_ids(claims.get("org_id")))
        if str(org_id).strip()
    }
    roles = {str(role) for role in claims.get("roles", []) if str(role).strip()}
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    context = FactoryAuthContext(
        subject=subject,
        org_ids=org_ids,
        roles=roles,
        claims=dict(claims),
        scheme=scheme,
    )
    request.state.factory_auth = context
    return context


def get_factory_auth(request: Request) -> FactoryAuthContext:
    context = getattr(request.state, "factory_auth", None)
    if context is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_auth_context")
    return context


def ensure_org_access(auth: FactoryAuthContext, org_id: UUID | str) -> None:
    normalized = str(org_id)
    if {"factory:admin", "admin", "owner"} & auth.roles:
        return
    if normalized not in auth.org_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="org_access_denied")


def _decode_clerk_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    jwks_client = PyJWKClient(settings.clerk_jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "RS384", "RS512", "EdDSA"],
        audience=settings.factory_jwt_audience or None,
        issuer=settings.clerk_issuer or settings.factory_jwt_issuer or None,
        options={"verify_aud": bool(settings.factory_jwt_audience)},
    )


def _coerce_org_ids(org_id: Any) -> list[str]:
    if org_id is None:
        return []
    if isinstance(org_id, list):
        return [str(item) for item in org_id]
    return [str(org_id)]
