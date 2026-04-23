"""Authentication helpers for packaged employee runtimes."""

from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import HTTPException, Request, WebSocket, status


@dataclass(slots=True)
class RuntimeAuthConfig:
    enabled: bool
    bearer_token: str


_DEFAULT_KEYS = {"", "forge-dev-key", "dev", "change-me"}


def _get_api_key() -> str:
    return os.environ.get("EMPLOYEE_API_KEY", "").strip()


def _is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "development") == "production"


def runtime_auth_config_from_dict(config: dict[str, object]) -> RuntimeAuthConfig:
    env_api_key = _get_api_key()
    bearer_token = env_api_key or str(config.get("api_auth_token", "")).strip()
    auth_required = bool(env_api_key) or bool(config.get("auth_required", bool(bearer_token)))
    return RuntimeAuthConfig(enabled=auth_required and bool(bearer_token), bearer_token=bearer_token)


def authorize_request(request: Request, config: RuntimeAuthConfig) -> None:
    if not config.enabled and not _is_production():
        return
    if not config.bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = _request_token(request)
    if token != config.bearer_token:
        detail = "Missing bearer token" if not token else "Invalid API key"
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def authorize_websocket(websocket: WebSocket, config: RuntimeAuthConfig) -> bool:
    if not config.enabled:
        return True
    if not config.bearer_token:
        await websocket.close(code=4401)
        return False
    token = websocket.query_params.get("token", "").strip()
    if token == config.bearer_token:
        return True
    await websocket.close(code=4401)
    return False


def _request_token(request: Request) -> str:
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return request.query_params.get("token", "").strip()
