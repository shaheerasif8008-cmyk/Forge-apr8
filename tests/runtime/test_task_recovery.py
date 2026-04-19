from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from employee_runtime.core.runtime_db import normalize_org_uuid
from factory.models.orm import (
    AuditEventRow,
    ClientOrgRow,
    ConversationRow,
    EmployeeTaskRow,
    MessageRow,
    OperationalMemoryRow,
)
from factory.pipeline.builder.entrypoint_generator import ENTRYPOINT_TEMPLATE
from factory.pipeline.evaluator.container_runner import find_free_port, wait_for_health
from tests.fixtures.sample_emails import CLEAR_QUALIFIED

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_ORG_ID = str(normalize_org_uuid("org-1"))
HOST_DATABASE_URL = "postgresql+asyncpg://forge:forge@localhost:5432/forge"
CONTAINER_DATABASE_URL = "postgresql+asyncpg://forge:forge@host.docker.internal:5432/forge"


def _docker_available() -> bool:
    result = subprocess.run(
        ["docker", "version"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


pytestmark = pytest.mark.skipif(not _docker_available(), reason="docker not available")


def _write_runtime_dockerfile(build_dir: Path) -> None:
    dockerfile = """FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential curl libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001
CMD ["python", "run.py"]
"""
    (build_dir / "Dockerfile").write_text(dockerfile)


def _write_requirements(build_dir: Path) -> None:
    dependencies = [
        "fastapi==0.136.0",
        "uvicorn[standard]==0.44.0",
        "python-multipart==0.0.26",
        "itsdangerous==2.2.0",
        "jinja2==3.1.6",
        "pydantic==2.12.5",
        "pydantic-settings==2.13.1",
        "email-validator>=2.3.0,<3",
        "httpx==0.28.1",
        "PyJWT==2.12.1",
        "langgraph==1.1.8",
        "instructor==1.15.1",
        "litellm==1.83.10",
        "sqlalchemy==2.0.49",
        "alembic==1.18.4",
        "asyncpg==0.31.0",
        "aiosqlite==0.22.1",
        "pgvector==0.4.2",
        "redis==7.4.0",
        "celery==5.6.3",
        "structlog==25.5.0",
        "langfuse>=4.3.1,<5",
    ]
    (build_dir / "requirements.txt").write_text("\n".join(dependencies) + "\n")


def _prepare_runtime_bundle(build_dir: Path) -> None:
    shutil.copytree(REPO_ROOT / "employee_runtime", build_dir / "employee_runtime")
    shutil.copytree(REPO_ROOT / "component_library", build_dir / "component_library")
    shutil.copytree(REPO_ROOT / "factory", build_dir / "factory")
    (build_dir / "generated").mkdir(parents=True, exist_ok=True)
    (build_dir / "generated" / "__init__.py").write_text("")
    (build_dir / "static").mkdir(parents=True, exist_ok=True)
    (build_dir / "static" / "index.html").write_text("<html><body>Forge Employee</body></html>")
    (build_dir / "run.py").write_text(ENTRYPOINT_TEMPLATE)
    _write_requirements(build_dir)
    _write_runtime_dockerfile(build_dir)

    config = {
        "employee_id": "arthur",
        "org_id": TEST_ORG_ID,
        "employee_name": "Arthur",
        "role_title": "Legal Intake Agent",
        "workflow": "legal_intake",
        "employee_database_url": CONTAINER_DATABASE_URL,
        "employee_db_auto_init": False,
        "static_dir": str(build_dir / "static"),
        "supervisor_email": "partner@example.com",
    }
    (build_dir / "config.yaml").write_text(json.dumps(config, indent=2, sort_keys=True))


async def _ensure_test_org() -> None:
    engine = create_async_engine(HOST_DATABASE_URL)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(
                lambda sync_conn: ClientOrgRow.metadata.create_all(
                    sync_conn,
                    tables=[
                        ClientOrgRow.__table__,
                        OperationalMemoryRow.__table__,
                        ConversationRow.__table__,
                        EmployeeTaskRow.__table__,
                        MessageRow.__table__,
                        AuditEventRow.__table__,
                    ],
                )
            )
            await conn.execute(
                text(
                    """
                    INSERT INTO client_orgs (id, name, slug, industry, tier, contact_email)
                    VALUES (:id, :name, :slug, :industry, :tier, :contact_email)
                    ON CONFLICT (id) DO NOTHING
                    """
                ),
                {
                    "id": TEST_ORG_ID,
                    "name": "Runtime Recovery Org",
                    "slug": "runtime-recovery-org",
                    "industry": "legal",
                    "tier": "enterprise",
                    "contact_email": "ops@example.com",
                },
            )
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_employee_container_marks_running_task_interrupted_after_kill_and_restart(
    tmp_path,
) -> None:
    build_dir = tmp_path / "runtime-bundle"
    image_tag = f"forge-runtime-recovery:{uuid4().hex}"
    container_name = f"forge-recovery-{uuid4().hex[:12]}"
    port = find_free_port()
    data_dir = tmp_path / "employee-data"
    build_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    try:
        _prepare_runtime_bundle(build_dir)

        subprocess.run(
            ["docker", "build", "-t", image_tag, "."],
            cwd=str(build_dir),
            capture_output=True,
            text=True,
            check=True,
        )
        container_id = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                container_name,
                "-p",
                f"{port}:8001",
                "-v",
                f"{data_dir}:/data",
                image_tag,
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        await _ensure_test_org()
        base_url = f"http://127.0.0.1:{port}"
        assert await wait_for_health(f"{base_url}/api/v1/health", timeout=120)

        async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
            memory_response = await client.patch(
                "/api/v1/memory/ops/pref:timezone",
                json={"value": {"timezone": "America/New_York"}, "category": "preference"},
            )
            assert memory_response.status_code == 200

            task_id = str(uuid4())
            request_task = asyncio.create_task(
                client.post(
                    "/api/v1/tasks",
                    json={
                        "task_id": task_id,
                        "input": CLEAR_QUALIFIED,
                        "context": {"_test_runtime_delay_seconds": 20},
                        "conversation_id": "default",
                    },
                    timeout=None,
                )
            )
            try:
                for _ in range(40):
                    task_response = await client.get(f"/api/v1/tasks/{task_id}")
                    if task_response.status_code == 200 and task_response.json()["status"] == "running":
                        break
                    await asyncio.sleep(0.25)
                else:
                    raise AssertionError("task never entered running state before kill")

                subprocess.run(["docker", "kill", container_id], capture_output=True, text=True, check=True)
            finally:
                with contextlib.suppress(Exception):
                    await request_task

        subprocess.run(["docker", "start", container_name], capture_output=True, text=True, check=True)
        assert await wait_for_health(f"{base_url}/api/v1/health", timeout=120)

        async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
            task_response = await client.get(f"/api/v1/tasks/{task_id}")
            assert task_response.status_code == 200
            task_payload = task_response.json()
            assert task_payload["status"] == "interrupted"
            assert task_payload["interruption_reason"] == "runtime_restarted_before_task_completion"

            approvals = await client.get("/api/v1/approvals")
            assert approvals.status_code == 200
            assert approvals.json() == []

            memory = await client.get("/api/v1/memory/ops?query=timezone")
            assert memory.status_code == 200
            assert any(entry["key"] == "pref:timezone" for entry in memory.json())

            history = await client.get("/api/v1/chat/history")
            assert history.status_code == 200
            messages = history.json()["messages"]
            assert any(message["role"] == "user" and CLEAR_QUALIFIED in message["content"] for message in messages)
            assert any(
                message["message_type"] == "status_update"
                and message["metadata"].get("task_id") == task_id
                and message["metadata"].get("status") == "interrupted"
                for message in messages
            )

            recovery = await client.get("/api/v1/runtime/recovery")
            assert recovery.status_code == 200
            assert task_id in recovery.json()["startup_summary"]["interrupted_task_ids"]
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, text=True)
        subprocess.run(["docker", "rmi", "-f", image_tag], capture_output=True, text=True)
