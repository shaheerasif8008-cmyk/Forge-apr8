"""Docker lifecycle helpers for evaluator and deployer stages."""

from __future__ import annotations

import asyncio
import os
import socket
import subprocess

import httpx


def find_free_port() -> int:
    """Return an available localhost TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        return int(sock.getsockname()[1])


async def start_container(
    image_tag: str,
    port: int,
    *,
    name: str | None = None,
    environment: str = "testing",
) -> str:
    """Start a container and return the container id."""
    command = ["docker", "run", "-d", "-p", f"{port}:8001", "-e", f"ENVIRONMENT={environment}"]
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY", "LANGFUSE_ENABLED"):
        value = os.environ.get(key, "")
        if value:
            command.extend(["-e", f"{key}={value}"])
    if name:
        command.extend(["--name", name])
    command.append(image_tag)
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    return result.stdout.strip()


async def stop_container(container_id: str) -> None:
    """Stop and remove a container, ignoring errors."""
    subprocess.run(["docker", "stop", container_id], capture_output=True, text=True)
    subprocess.run(["docker", "rm", container_id], capture_output=True, text=True)


async def wait_for_health(url: str, timeout: int = 60) -> bool:
    """Poll a health endpoint until it reports healthy or times out."""
    deadline = asyncio.get_event_loop().time() + timeout
    delay = 0.5
    async with httpx.AsyncClient(timeout=5.0) as client:
        while asyncio.get_event_loop().time() < deadline:
            try:
                response = await client.get(url)
                if response.status_code == 200 and response.json().get("status") == "ok":
                    return True
            except httpx.HTTPError:
                pass
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, 3.0)
    return False
