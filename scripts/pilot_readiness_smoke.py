#!/usr/bin/env python3
"""Run the pilot-readiness smoke check for a packaged employee runtime.

The smoke runs in-process against the standard employee FastAPI app. It is not a
replacement for server-export sovereignty proof; it verifies the daily-use API
surface that the employee app and operator runbooks depend on.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from employee_runtime.core.api import create_employee_app

PILOT_TOKEN = "pilot-runtime-token"
PILOT_EMAIL = (
    "My name is Sarah Johnson. I was injured in a car accident on February 15, "
    "2026. The other driver ran a red light and I have $45,000 in medical bills. "
    "Phone: (555) 123-4567. Email: sarah.johnson@example.com."
)


@dataclass
class SmokeCheck:
    name: str
    status: str
    detail: dict[str, Any] = field(default_factory=dict)


def _pilot_manifest() -> dict[str, Any]:
    return {
        "employee_id": "pilot-legal-intake",
        "org_id": "org-pilot",
        "employee_name": "Arthur",
        "role_title": "Legal Intake Associate",
        "workflow": "legal_intake",
        "risk_tier": "LOW",
        "tool_permissions": ["email_tool", "file_storage_tool", "document_ingestion"],
        "components": [
            {
                "id": "litellm_router",
                "category": "models",
                "config": {
                    "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
                    "fallback_model": "openrouter/anthropic/claude-3.5-haiku",
                },
            },
            {"id": "text_processor", "category": "work", "config": {}},
            {"id": "document_analyzer", "category": "work", "config": {}},
            {"id": "draft_generator", "category": "work", "config": {}},
            {"id": "email_tool", "category": "tools", "config": {"provider": "fixture"}},
            {"id": "file_storage_tool", "category": "tools", "config": {"provider": "memory"}},
            {"id": "document_ingestion", "category": "tools", "config": {}},
            {"id": "operational_memory", "category": "data", "config": {}},
            {"id": "working_memory", "category": "data", "config": {}},
            {"id": "context_assembler", "category": "data", "config": {}},
            {"id": "org_context", "category": "data", "config": {}},
            {
                "id": "knowledge_base",
                "category": "data",
                "config": {"embedder": lambda _: [0.1] * 1536},
            },
            {"id": "confidence_scorer", "category": "quality", "config": {}},
            {"id": "audit_system", "category": "quality", "config": {}},
            {"id": "autonomy_manager", "category": "quality", "config": {}},
            {"id": "explainability", "category": "quality", "config": {}},
            {"id": "input_protection", "category": "quality", "config": {}},
            {"id": "verification_layer", "category": "quality", "config": {}},
        ],
        "identity_layers": {
            "layer_1_core_identity": "You are a Forge AI Employee.",
            "layer_2_role_definition": "You are Arthur, Legal Intake Associate.",
            "layer_3_organizational_map": "Report to Dana Cartwright.",
            "layer_4_behavioral_rules": "Direct commands override portal rules.",
            "layer_5_retrieved_context": "",
            "layer_6_self_awareness": "You can process legal intake, manage memory, and request approvals.",
        },
        "ui": {
            "app_badge": "Pilot server export",
            "capabilities": ["process legal intake", "manage memory", "request approvals"],
        },
        "org_map": [
            {
                "name": "Dana Cartwright",
                "role": "Managing Partner",
                "email": "dana.cartwright@example.com",
                "relationship": "supervisor",
                "communication_preference": "email",
            }
        ],
    }


def _runtime_config() -> dict[str, Any]:
    return {
        "manifest": _pilot_manifest(),
        "auth_required": True,
        "api_auth_token": PILOT_TOKEN,
        "supervisor_email": "dana.cartwright@example.com",
        "deployment_format": "server",
        "practice_areas": ["personal injury", "employment", "commercial dispute"],
        "default_attorney": "Dana Cartwright",
        "email_fixtures": [
            {
                "id": "pilot-msg-1",
                "from": "sarah.johnson@example.com",
                "subject": "Car accident intake",
                "body": PILOT_EMAIL,
                "read": False,
            }
        ],
    }


async def _record(
    checks: list[SmokeCheck],
    name: str,
    response_status: int,
    *,
    expected: int = 200,
    detail: dict[str, Any] | None = None,
) -> None:
    checks.append(
        SmokeCheck(
            name=name,
            status="passed" if response_status == expected else "failed",
            detail={"status_code": response_status, "expected": expected, **(detail or {})},
        )
    )


async def _degraded_integrations(app: Any) -> list[dict[str, Any]]:
    service = app.state.runtime_service
    degraded: list[dict[str, Any]] = []
    for component_id, component in service.components.items():
        if not component_id.endswith("_tool"):
            continue
        health = await component.health_check()
        detail = health.detail.lower()
        if any(marker in detail for marker in ("fixture", "memory", "fallback", "inmemory", "provider=memory")):
            degraded.append(
                {
                    "component_id": component_id,
                    "health": health.model_dump(),
                    "launch_note": "Allowed for pilot only when disclosed in the handoff report.",
                }
            )
    return degraded


async def run_pilot_smoke() -> dict[str, Any]:
    previous_environment = os.environ.get("ENVIRONMENT")
    os.environ["ENVIRONMENT"] = "development"
    app = create_employee_app("pilot-legal-intake", _runtime_config())
    checks: list[SmokeCheck] = []
    headers = {"Authorization": f"Bearer {PILOT_TOKEN}"}
    task_id = ""

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://pilot") as client:
            response = await client.get("/api/v1/health")
            await _record(checks, "health_public", response.status_code)

            response = await client.get("/api/v1/chat/history")
            await _record(checks, "auth_unauthorized", response.status_code, expected=401)

            response = await client.get("/api/v1/chat/history", headers=headers)
            await _record(checks, "auth_authorized_history", response.status_code)

            response = await client.get("/api/v1/meta", headers=headers)
            await _record(checks, "meta", response.status_code, detail=response.json() if response.status_code == 200 else {})

            response = await client.post(
                "/api/v1/tasks",
                headers=headers,
                json={"input": PILOT_EMAIL, "context": {"input_type": "email"}, "conversation_id": "default"},
            )
            payload = response.json() if response.status_code == 200 else {}
            task_id = str(payload.get("task_id", ""))
            await _record(checks, "task_submit", response.status_code, detail={"task_id": task_id, "status": payload.get("status")})

            response = await client.get(f"/api/v1/tasks/{task_id}/brief", headers=headers)
            await _record(checks, "task_brief", response.status_code)

            response = await client.post(
                f"/api/v1/tasks/{task_id}/corrections",
                headers=headers,
                json={"message": "Qualification should mention medical bills.", "corrected_output": "Include medical bills in the summary."},
            )
            await _record(checks, "correction", response.status_code)

            response = await client.patch(
                "/api/v1/memory/ops/pref:pilot",
                headers=headers,
                json={"value": {"channel": "email", "cadence": "daily"}, "category": "preference"},
            )
            await _record(checks, "memory_update", response.status_code)

            response = await client.patch(
                "/api/v1/settings",
                headers=headers,
                json={"values": {"advanced": {"learning_enabled": True}}},
            )
            await _record(checks, "settings_patch", response.status_code)

            response = await client.post(
                "/api/v1/behavior/direct-commands",
                headers=headers,
                json={"command": "Do not send non-urgent email after 5 PM."},
            )
            behavior_ok = response.status_code
            resolution = await client.get(
                "/api/v1/behavior/resolution?channel=email&urgency=normal&current_time=2026-04-26T22:00:00",
                headers=headers,
            )
            status = 200 if behavior_ok == 200 and resolution.status_code == 200 and resolution.json().get("applies") else 500
            await _record(checks, "behavior_direct_command", status)

            response = await client.post(
                "/api/v1/documents/upload",
                headers=headers,
                files={"file": ("pilot-playbook.txt", b"Pilot playbook\n\nEscalate urgent matters.", "text/plain")},
                data={"metadata": json.dumps({"title": "Pilot Playbook"})},
            )
            await _record(checks, "document_upload", response.status_code)

            response = await client.post(
                "/api/v1/autonomy/daily-loop",
                headers=headers,
                json={"conversation_id": "default", "max_items": 0},
            )
            await _record(checks, "daily_loop", response.status_code)

            response = await client.get("/api/v1/metrics/dashboard", headers=headers)
            await _record(checks, "metrics_dashboard", response.status_code)

            response = await client.get("/api/v1/updates", headers=headers)
            await _record(checks, "updates", response.status_code)

        degraded = await _degraded_integrations(app)
        checks.append(
            SmokeCheck(
                name="integration_degraded_inventory",
                status="passed" if degraded else "failed",
                detail={"degraded_count": len(degraded)},
            )
        )
        passed = all(check.status == "passed" for check in checks)
        return {
            "overall": "passed" if passed else "failed",
            "checks": [check.__dict__ for check in checks],
            "production_guards": {
                "auth_required": True,
                "unauthorized_status": next(
                    check.detail["status_code"] for check in checks if check.name == "auth_unauthorized"
                ),
                "runtime_token_source": "generated employee package config",
            },
            "degraded_integrations_policy": "allowed_for_pilot_with_disclosure",
            "degraded_integrations": degraded,
            "next_required_proof": "Run scripts/prove_server_export.py --mode full for Docker sovereignty proof.",
        }
    finally:
        await app.state.runtime_service.shutdown()
        if previous_environment is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = previous_environment


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    with redirect_stdout(sys.stderr):
        report = asyncio.run(run_pilot_smoke())
    print(json.dumps(report, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if report["overall"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
