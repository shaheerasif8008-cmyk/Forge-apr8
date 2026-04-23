"""file_storage_tool integration component."""

from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Any

import structlog

from component_library.interfaces import (
    ComponentHealth,
    ComponentInitializationError,
    ToolIntegration,
    strict_providers_enabled,
)
from component_library.registry import register
from component_library.tools.adapter_runtime import InMemoryProviderAdapter

try:  # pragma: no cover - optional dependency
    import boto3
except Exception:  # pragma: no cover - optional dependency
    boto3 = None

logger = structlog.get_logger(__name__)


@register("file_storage_tool")
class FileStorageTool(ToolIntegration):
    config_schema = {
        "provider": {"type": "str", "required": False, "description": "Storage backend: s3 | local | memory.", "default": "local"},
        "tenant_id": {"type": "str", "required": False, "description": "Tenant prefix for storage isolation.", "default": "default-tenant"},
        "bucket": {"type": "str", "required": False, "description": "S3/MinIO bucket name.", "default": "forge-artifacts"},
        "root_dir": {"type": "str", "required": False, "description": "Local filesystem root for local storage.", "default": ".forge_storage"},
        "endpoint_url": {"type": "str", "required": False, "description": "S3-compatible endpoint (e.g. http://minio:9000).", "default": ""},
        "aws_access_key_id": {"type": "str", "required": False, "description": "S3 access key override.", "default": ""},
        "aws_secret_access_key": {"type": "str", "required": False, "description": "S3 secret key override.", "default": ""},
        "region_name": {"type": "str", "required": False, "description": "S3 region name.", "default": ""},
    }
    component_id = "file_storage_tool"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._provider = str(config.get("provider", "local"))
        self._tenant_id = str(config.get("tenant_id", "default-tenant"))
        self._bucket = str(config.get("bucket", "forge-artifacts"))
        self._root = Path(config.get("root_dir", ".forge_storage")).expanduser().resolve()
        self._adapter = InMemoryProviderAdapter(self._provider)
        self._memory_store: dict[str, bytes] = {}
        self._s3_client = None
        s3_access_key = str(config.get("aws_access_key_id") or os.getenv("AWS_ACCESS_KEY_ID") or "")
        s3_secret_key = str(config.get("aws_secret_access_key") or os.getenv("AWS_SECRET_ACCESS_KEY") or "")
        if self._provider == "s3" and boto3 is not None and s3_access_key and s3_secret_key:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=config.get("endpoint_url"),
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key,
                region_name=config.get("region_name"),
            )
        self._fallback_active = self._provider == "s3" and self._s3_client is None
        if self._fallback_active:
            logger.warning(
                "component_fallback_active",
                component="file_storage_tool",
                reason=(
                    "S3 provider requested but boto3 not installed or credentials missing; "
                    "using local storage"
                ),
            )
            if strict_providers_enabled():
                raise ComponentInitializationError(
                    "file_storage_tool: boto3 and S3 credentials required when "
                    "FORGE_STRICT_PROVIDERS=true"
                )
        self._root.mkdir(parents=True, exist_ok=True)

    async def health_check(self) -> ComponentHealth:
        if self._fallback_active:
            return ComponentHealth(
                healthy=False,
                detail="fallback_mode: s3 requested but boto3 unavailable; using local filesystem",
            )
        mode = "s3" if self._s3_client is not None else self._provider
        return ComponentHealth(healthy=True, detail=f"provider={mode}; tenant={self._tenant_id}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/tools/test_file_storage_tool.py"]

    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        if action == "upload":
            return await self._upload(params)
        if action == "download":
            return await self._download(params)
        if action == "list":
            return await self._list(params)
        if action == "delete":
            return await self._delete(params)
        raise ValueError(f"Unsupported file storage action: {action}")

    async def _upload(self, params: dict[str, Any]) -> dict[str, Any]:
        key = self._scoped_key(str(params["key"]))
        content = self._normalize_bytes(params)
        if self._s3_client is not None:
            self._s3_client.put_object(Bucket=self._bucket, Key=key, Body=content)
        elif self._provider == "memory":
            self._memory_store[key] = content
        else:
            path = self._root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        self._adapter.touch()
        return {"key": key, "size_bytes": len(content), **self._adapter.metadata()}

    async def _download(self, params: dict[str, Any]) -> dict[str, Any]:
        key = self._scoped_key(str(params["key"]))
        if self._s3_client is not None:
            body = self._s3_client.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        elif self._provider == "memory":
            body = self._memory_store.get(key, b"")
        else:
            path = self._root / key
            body = path.read_bytes() if path.exists() else b""
        self._adapter.touch()
        return {
            "key": key,
            "content": body.decode("utf-8", errors="replace"),
            "content_base64": base64.b64encode(body).decode("ascii"),
            "exists": bool(body),
            **self._adapter.metadata(),
        }

    async def _list(self, params: dict[str, Any]) -> dict[str, Any]:
        prefix = self._scoped_key(str(params.get("prefix", "")).lstrip("/"))
        if self._s3_client is not None:
            response = self._s3_client.list_objects_v2(Bucket=self._bucket, Prefix=prefix)
            items = [{"key": obj["Key"], "size_bytes": obj.get("Size", 0)} for obj in response.get("Contents", [])]
        elif self._provider == "memory":
            items = [
                {"key": key, "size_bytes": len(content)}
                for key, content in self._memory_store.items()
                if key.startswith(prefix)
            ]
        else:
            items = []
            base = self._root / prefix
            if base.exists() and base.is_dir():
                for path in sorted(base.rglob("*")):
                    if path.is_file():
                        relative = path.relative_to(self._root).as_posix()
                        items.append({"key": relative, "size_bytes": path.stat().st_size})
            elif prefix:
                for path in sorted(self._root.rglob("*")):
                    if path.is_file():
                        relative = path.relative_to(self._root).as_posix()
                        if relative.startswith(prefix):
                            items.append({"key": relative, "size_bytes": path.stat().st_size})
        self._adapter.touch()
        return {"items": items, **self._adapter.metadata()}

    async def _delete(self, params: dict[str, Any]) -> dict[str, Any]:
        key = self._scoped_key(str(params["key"]))
        deleted = False
        if self._s3_client is not None:
            self._s3_client.delete_object(Bucket=self._bucket, Key=key)
            deleted = True
        elif self._provider == "memory":
            deleted = self._memory_store.pop(key, None) is not None
        else:
            path = self._root / key
            if path.exists():
                path.unlink()
                deleted = True
        self._adapter.touch()
        return {"key": key, "deleted": deleted, **self._adapter.metadata()}

    def _normalize_bytes(self, params: dict[str, Any]) -> bytes:
        if "content_bytes" in params:
            value = params["content_bytes"]
            if isinstance(value, bytes):
                return value
            return bytes(value)
        if "content_base64" in params:
            return base64.b64decode(params["content_base64"])
        return str(params.get("content", "")).encode("utf-8")

    def _scoped_key(self, key: str) -> str:
        key = key.lstrip("/")
        return f"{self._tenant_id}/{key}" if key else f"{self._tenant_id}/"
