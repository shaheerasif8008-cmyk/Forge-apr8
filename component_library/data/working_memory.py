"""working_memory data source component."""

from __future__ import annotations

import json
import time
from typing import Any

from redis.asyncio import Redis

from component_library.interfaces import ComponentHealth, DataSource
from component_library.registry import register


@register("working_memory")
class WorkingMemory(DataSource):
    component_id = "working_memory"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._org_id = config.get("org_id", "")
        self._employee_id = config.get("employee_id", "")
        self._ttl_seconds = int(config.get("ttl_seconds", 60 * 60 * 24))
        self._redis: Redis | None = None
        self._in_memory: dict[str, tuple[float, Any]] = {}
        redis_url = config.get("redis_url")
        redis_client = config.get("redis_client")
        if redis_client is not None:
            self._redis = redis_client
        elif redis_url:
            self._redis = Redis.from_url(redis_url, decode_responses=True)

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/data/test_working_memory.py"]

    async def query(self, query: str, **kwargs: Any) -> Any:
        task_id = kwargs.get("task_id", "")
        return await self.get_context(task_id, query)

    def _key(self, task_id: str, key: str) -> str:
        return f"wm:{self._org_id}:{self._employee_id}:{task_id}:{key}"

    async def set_context(self, task_id: str, key: str, value: Any) -> None:
        full_key = self._key(task_id, key)
        if self._redis is not None:
            await self._redis.set(full_key, json.dumps(value), ex=self._ttl_seconds)
            return
        self._in_memory[full_key] = (time.time() + self._ttl_seconds, value)

    async def get_context(self, task_id: str, key: str) -> Any:
        full_key = self._key(task_id, key)
        if self._redis is not None:
            value = await self._redis.get(full_key)
            return json.loads(value) if value is not None else None
        record = self._in_memory.get(full_key)
        if record is None:
            return None
        expiry, value = record
        if expiry < time.time():
            self._in_memory.pop(full_key, None)
            return None
        return value

    async def get_all(self, task_id: str) -> dict[str, Any]:
        prefix = self._key(task_id, "")
        if self._redis is not None:
            keys = await self._redis.keys(f"{prefix}*")
            result: dict[str, Any] = {}
            for key in keys:
                value = await self._redis.get(key)
                if value is not None:
                    result[key.rsplit(":", 1)[-1]] = json.loads(value)
            return result
        now = time.time()
        result = {}
        for key, (expiry, value) in list(self._in_memory.items()):
            if not key.startswith(prefix):
                continue
            if expiry < now:
                self._in_memory.pop(key, None)
                continue
            result[key.rsplit(":", 1)[-1]] = value
        return result

    async def clear_task(self, task_id: str) -> None:
        prefix = self._key(task_id, "")
        if self._redis is not None:
            keys = await self._redis.keys(f"{prefix}*")
            if keys:
                await self._redis.delete(*keys)
            return
        for key in list(self._in_memory.keys()):
            if key.startswith(prefix):
                self._in_memory.pop(key, None)
