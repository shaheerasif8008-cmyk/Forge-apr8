#!/usr/bin/env python3
"""Run the server-export deployment proof against a live Forge stack."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_API = "http://localhost:8000/api/v1"
DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"
DEFAULT_EMPLOYEE_KEY = "proof-employee-key"
DOCKER_CLI_CANDIDATES = (
    "/usr/local/bin/docker",
    "/Applications/Docker.app/Contents/Resources/bin/docker",
)
DOCKER_PATH_DIRS = (
    "/usr/local/bin",
    "/Applications/Docker.app/Contents/Resources/bin",
)
SUCCESS_BUILD_STATUSES = {"pending_client_action", "deployed"}
FAIL_BUILD_STATUSES = {"failed"}
FINAL_TASK_STATUSES = {"completed", "failed", "awaiting_approval"}


@dataclass
class ProofContext:
    api_base: str
    factory_env: dict[str, str]
    employee_env: dict[str, str]
    auth_token: str = ""
    build_id: str = ""
    artifact_path: str = ""
    employee_url: str = ""
    employee_key: str = DEFAULT_EMPLOYEE_KEY
    bundle_dir: str = ""
    events: list[dict[str, object]] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def record(self, step: str, **detail: object) -> None:
        self.events.append({"step": step, **detail})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=DEFAULT_API)
    parser.add_argument(
        "--mode",
        choices=("preflight", "full"),
        default="full",
        help="Run only environment validation or attempt the full proof.",
    )
    parser.add_argument(
        "--bundle-dir",
        default="",
        help="Optional directory for extracted handoff bundle. Defaults to a temp dir.",
    )
    return parser.parse_args()


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def _merged_env() -> dict[str, str]:
    file_env = _load_env_file(REPO_ROOT / ".env")
    merged = dict(file_env)
    for key, value in os.environ.items():
        if value:
            merged[key] = value
    return merged


def _docker_cli() -> str | None:
    docker = shutil.which("docker")
    if docker:
        return docker
    for candidate in DOCKER_CLI_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    return None


def _resolve_command(command: list[str]) -> list[str]:
    if command and command[0] == "docker":
        docker = _docker_cli()
        if docker:
            return [docker, *command[1:]]
    return command


def _command_env() -> dict[str, str]:
    env = os.environ.copy()
    path_parts = [part for part in env.get("PATH", "").split(os.pathsep) if part]
    for docker_dir in reversed(DOCKER_PATH_DIRS):
        if Path(docker_dir).exists() and docker_dir not in path_parts:
            path_parts.insert(0, docker_dir)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


def _run(command: list[str], *, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        _resolve_command(command),
        cwd=str(cwd or REPO_ROOT),
        env=_command_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _request_json(
    method: str,
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode()
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return exc.code, payload


def _request_text(url: str, *, timeout: int = 10) -> tuple[int, str]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


def _docker_ready() -> tuple[bool, str]:
    if _docker_cli() is None:
        return False, "docker CLI not found on PATH"
    result = _run(["docker", "info"], timeout=30)
    if result.returncode == 0:
        return True, "docker daemon reachable"
    detail = (result.stderr or result.stdout).strip().splitlines()
    return False, detail[-1] if detail else "docker daemon unavailable"


def _compose_config_ok() -> tuple[bool, str]:
    result = _run(["docker", "compose", "config", "--quiet"], timeout=60)
    if result.returncode == 0:
        return True, "docker compose config valid"
    detail = (result.stderr or result.stdout).strip().splitlines()
    return False, detail[-1] if detail else "docker compose config failed"


def _preflight(ctx: ProofContext) -> bool:
    env = ctx.factory_env
    has_model_key = bool(env.get("ANTHROPIC_API_KEY") or env.get("OPENAI_API_KEY") or env.get("OPENROUTER_API_KEY"))
    if not has_model_key:
        ctx.blockers.append("No ANTHROPIC_API_KEY or OPENROUTER_API_KEY configured.")
    if not env.get("FACTORY_JWT_SECRET"):
        ctx.blockers.append("FACTORY_JWT_SECRET is missing.")

    docker_ok, docker_detail = _docker_ready()
    ctx.record("docker", healthy=docker_ok, detail=docker_detail)
    if not docker_ok:
        ctx.blockers.append(f"Docker unavailable: {docker_detail}")
    else:
        compose_ok, compose_detail = _compose_config_ok()
        ctx.record("compose_config", healthy=compose_ok, detail=compose_detail)
        if not compose_ok:
            ctx.blockers.append(f"docker compose config failed: {compose_detail}")

    return not ctx.blockers


def _start_stack(ctx: ProofContext) -> None:
    result = _run(["docker", "compose", "up", "-d", "--build"], timeout=1200)
    if result.returncode != 0:
        raise RuntimeError(f"docker compose up failed: {(result.stderr or result.stdout)[-2000:]}")

    deadline = time.time() + 180
    while time.time() < deadline:
        status, _ = _request_text(f"{ctx.api_base}/health", timeout=5)
        if status == 200:
            ctx.record("factory_health", status_code=status)
            return
        time.sleep(2)
    raise RuntimeError("Factory health check did not return 200 within 180 seconds.")


def _ensure_proof_org(ctx: ProofContext) -> None:
    sql = (
        "INSERT INTO client_orgs (id, name, slug, industry, tier, contact_email) "
        f"VALUES ('{DEFAULT_ORG_ID}', 'Cartwright Law', 'cartwright-law-proof', "
        "'legal', 'enterprise', 'dana.cartwright@example.com') "
        "ON CONFLICT (id) DO NOTHING;"
    )
    result = _run(
        ["docker", "compose", "exec", "-T", "postgres", "psql", "-U", "forge", "-d", "forge", "-c", sql],
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Proof org seed failed: {(result.stderr or result.stdout)[-2000:]}")
    ctx.record("proof_org", org_id=DEFAULT_ORG_ID)


def _issue_factory_token(ctx: ProofContext) -> None:
    secret = ctx.factory_env["FACTORY_JWT_SECRET"]
    status, payload = _request_json(
        "POST",
        f"{ctx.api_base}/auth/token",
        payload={
            "api_key": secret,
            "subject": "server-export-proof",
            "org_ids": [DEFAULT_ORG_ID],
        },
    )
    if status != 200 or not payload.get("access_token"):
        raise RuntimeError(f"Factory token request failed: HTTP {status} {payload}")
    ctx.auth_token = str(payload["access_token"])
    ctx.record("factory_token", status_code=status)


def _commission_build(ctx: ProofContext) -> None:
    headers = {"Authorization": f"Bearer {ctx.auth_token}"}
    status, payload = _request_json(
        "POST",
        f"{ctx.api_base}/commissions",
        headers=headers,
        payload={
            "org_id": DEFAULT_ORG_ID,
            "employee_type": "legal_intake_associate",
            "name": "Cartwright Intake Associate",
            "role_title": "Legal Intake Associate",
            "role_summary": (
                "Triages inbound legal intake emails, extracts facts, flags urgency, "
                "and prepares structured intake briefs for partner review."
            ),
            "primary_responsibilities": [
                "triage inbound intake emails",
                "extract claimant facts and contact info",
                "prepare partner-facing intake briefs",
            ],
            "kpis": ["triage latency", "brief completeness", "urgency recall"],
            "required_tools": ["email", "messaging"],
            "required_data_sources": ["conflicts_csv"],
            "communication_channels": ["email", "slack", "app"],
            "risk_tier": "high",
            "deployment_format": "server",
            "deployment_target": "client_server",
            "supervisor_email": "dana.cartwright@example.com",
            "org_context": {
                "firm_info": {
                    "name": "Cartwright Law",
                    "practice_areas": ["wrongful termination", "wage disputes", "harassment"],
                },
                "default_attorney": "Dana Cartwright",
                "people": [
                    {
                        "name": "Dana Cartwright",
                        "role": "Managing Partner",
                        "email": "dana.cartwright@example.com",
                        "preferred_channel": "slack",
                        "communication_style": "urgent and concise",
                        "relationship": "supervisor",
                    }
                ],
            },
            "org_map": [
                {
                    "name": "Dana Cartwright",
                    "role": "Managing Partner",
                    "email": "dana.cartwright@example.com",
                    "preferred_channel": "slack",
                    "communication_style": "urgent and concise",
                    "relationship": "supervisor",
                }
            ],
            "authority_matrix": {
                "send_outbound_email": "requires_approval",
                "accept_client": "requires_approval",
                "reject_client": "requires_approval",
            },
            "raw_intake": (
                "Cartwright Law is a 10-attorney employment law firm. "
                "Flag statute-of-limitations issues and deadline language immediately. "
                "Conflict check against a CSV list of current clients."
            ),
        },
    )
    if status != 202 or not payload.get("build_id"):
        raise RuntimeError(f"Commission request failed: HTTP {status} {payload}")
    ctx.build_id = str(payload["build_id"])
    ctx.record("commission", status_code=status, build_id=ctx.build_id)


def _get_build(ctx: ProofContext) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {ctx.auth_token}"}
    status, payload = _request_json("GET", f"{ctx.api_base}/builds/{ctx.build_id}", headers=headers)
    if status != 200:
        raise RuntimeError(f"Build status request failed: HTTP {status} {payload}")
    return payload


def _approve_build(ctx: ProofContext) -> None:
    headers = {"Authorization": f"Bearer {ctx.auth_token}"}
    status, payload = _request_json("POST", f"{ctx.api_base}/builds/{ctx.build_id}/approve", headers=headers, payload={})
    if status != 200:
        raise RuntimeError(f"Build approval failed: HTTP {status} {payload}")
    ctx.record("approve_build", status_code=status)


def _wait_for_build(ctx: ProofContext) -> dict[str, Any]:
    deadline = time.time() + 3600
    approved = False
    while time.time() < deadline:
        try:
            build = _get_build(ctx)
        except (TimeoutError, OSError, socket.timeout, urllib.error.URLError) as exc:
            ctx.record("build_status_poll", healthy=False, detail=str(exc))
            time.sleep(20)
            continue
        status = str(build.get("status", ""))
        ctx.record("build_status", status=status)
        if status == "pending_review" and not approved:
            _approve_build(ctx)
            approved = True
        elif status in SUCCESS_BUILD_STATUSES:
            return build
        elif status in FAIL_BUILD_STATUSES:
            raise RuntimeError(f"Build failed: {build.get('logs', [])[-5:]}")
        time.sleep(20)
    raise RuntimeError("Timed out waiting for build to reach a terminal export state.")


def _extract_bundle(ctx: ProofContext, build: dict[str, Any], bundle_dir_arg: str) -> Path:
    metadata = build.get("metadata", {})
    bundles = metadata.get("deployment_bundles", {}) if isinstance(metadata, dict) else {}
    server_bundle = bundles.get("server", {}) if isinstance(bundles, dict) else {}
    artifact_path = str(
        server_bundle.get("artifact_path")
        or metadata.get("artifact_path")
        or ""
    )
    if not artifact_path:
        for artifact in build.get("artifacts", []):
            if artifact.get("artifact_type") == "server_package":
                artifact_path = str(artifact.get("location", ""))
                break
    if not artifact_path:
        raise RuntimeError("No server package artifact path found in build payload.")
    archive_path = _resolve_artifact_archive(ctx, artifact_path)

    target_dir = Path(bundle_dir_arg) if bundle_dir_arg else Path(tempfile.mkdtemp(prefix="forge-server-proof-"))
    target_dir.mkdir(parents=True, exist_ok=True)
    if archive_path.suffix == ".zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(target_dir)
    else:
        raise RuntimeError(f"Unsupported server package format: {archive_path.name}")

    ctx.artifact_path = str(archive_path)
    ctx.bundle_dir = str(target_dir)
    ctx.record("bundle_extract", artifact_path=ctx.artifact_path, bundle_dir=ctx.bundle_dir)
    return target_dir


def _resolve_artifact_archive(ctx: ProofContext, artifact_path: str) -> Path:
    archive_path = Path(artifact_path)
    if archive_path.exists():
        return archive_path

    export_dir = Path(tempfile.mkdtemp(prefix="forge-server-artifact-"))
    copied_path = export_dir / archive_path.name
    result = _run(
        ["docker", "compose", "cp", f"pipeline-worker:{artifact_path}", str(copied_path)],
        timeout=120,
    )
    if result.returncode != 0 or not copied_path.exists():
        raise RuntimeError(
            "Server package not found on host or pipeline-worker container: "
            f"{archive_path}; copy output={(result.stderr or result.stdout)[-1000:]}"
        )
    ctx.record("artifact_copy", source=f"pipeline-worker:{artifact_path}", copied_path=str(copied_path))
    return copied_path


def _write_bundle_env(ctx: ProofContext, bundle_dir: Path) -> None:
    example_path = bundle_dir / ".env.example"
    env_path = bundle_dir / ".env"
    if not example_path.exists():
        raise RuntimeError(f"Bundle missing .env.example: {example_path}")
    env_data = _load_env_file(example_path)
    for key in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        if ctx.factory_env.get(key):
            env_data[key] = ctx.factory_env[key]
    env_data["EMPLOYEE_API_KEY"] = ctx.employee_key
    env_path.write_text("".join(f"{key}={value}\n" for key, value in sorted(env_data.items())))
    ctx.record("bundle_env", env_path=str(env_path))


def _read_host_port(bundle_dir: Path) -> int:
    compose_text = (bundle_dir / "docker-compose.yml").read_text()
    for line in compose_text.splitlines():
        stripped = line.strip().strip('"').strip("'")
        if ":" in stripped and stripped[0].isdigit():
            host = stripped.split(":", 1)[0]
            try:
                return int(host)
            except ValueError:
                continue
    return 8001


def _start_employee_bundle(ctx: ProofContext, bundle_dir: Path) -> None:
    result = _run(["docker", "compose", "up", "-d", "--build"], cwd=bundle_dir, timeout=1800)
    if result.returncode != 0:
        raise RuntimeError(f"Bundle docker compose up failed: {(result.stderr or result.stdout)[-3000:]}")
    port = _read_host_port(bundle_dir)
    ctx.employee_url = f"http://localhost:{port}"

    deadline = time.time() + 180
    while time.time() < deadline:
        status, _ = _request_text(f"{ctx.employee_url}/api/v1/health", timeout=5)
        if status == 200:
            ctx.record("employee_health", status_code=status, employee_url=ctx.employee_url)
            return
        time.sleep(2)
    raise RuntimeError("Employee bundle health check did not return 200 within 180 seconds.")


def _submit_task(ctx: ProofContext, email_body: str) -> str:
    headers = {"Authorization": f"Bearer {ctx.employee_key}"}
    status, payload = _request_json(
        "POST",
        f"{ctx.employee_url}/api/v1/tasks",
        headers=headers,
        payload={"input": email_body, "context": {"input_type": "email"}, "conversation_id": "default"},
        timeout=60,
    )
    if status != 200 or not payload.get("task_id"):
        raise RuntimeError(f"Employee task submission failed: HTTP {status} {payload}")
    task_id = str(payload["task_id"])
    ctx.record("task_submit", task_id=task_id, status_code=status)
    return task_id


def _wait_for_task(ctx: ProofContext, task_id: str) -> dict[str, Any]:
    deadline = time.time() + 180
    while time.time() < deadline:
        status_code, payload = _request_json(
            "GET",
            f"{ctx.employee_url}/api/v1/tasks/{task_id}",
            headers={"Authorization": f"Bearer {ctx.employee_key}"},
            timeout=30,
        )
        if status_code != 200:
            raise RuntimeError(f"Task polling failed: HTTP {status_code} {payload}")
        status = str(payload.get("status", payload.get("state", "")))
        ctx.record("task_status", task_id=task_id, status=status)
        if status in FINAL_TASK_STATUSES:
            return payload
        time.sleep(5)
    raise RuntimeError(f"Timed out waiting for task {task_id} to finish.")


def _get_brief(ctx: ProofContext, task_id: str) -> dict[str, Any]:
    status, payload = _request_json(
        "GET",
        f"{ctx.employee_url}/api/v1/tasks/{task_id}/brief",
        headers={"Authorization": f"Bearer {ctx.employee_key}"},
        timeout=30,
    )
    if status != 200:
        raise RuntimeError(f"Brief request failed: HTTP {status} {payload}")
    ctx.record("task_brief", task_id=task_id)
    return payload


def _stop_factory_stack() -> None:
    result = _run(["docker", "compose", "stop", "factory", "pipeline-worker"], timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"Stopping factory stack failed: {(result.stderr or result.stdout)[-2000:]}")


def _report(ctx: ProofContext) -> str:
    return json.dumps(
        {
            "api_base": ctx.api_base,
            "build_id": ctx.build_id,
            "artifact_path": ctx.artifact_path,
            "bundle_dir": ctx.bundle_dir,
            "employee_url": ctx.employee_url,
            "events": ctx.events,
            "blockers": ctx.blockers,
        },
        indent=2,
        sort_keys=True,
    )


def main() -> int:
    args = _parse_args()
    merged_env = _merged_env()
    ctx = ProofContext(api_base=args.api_base.rstrip("/"), factory_env=merged_env, employee_env=merged_env)

    ready = _preflight(ctx)
    if args.mode == "preflight" or not ready:
        print(_report(ctx))
        return 0 if ready else 2

    urgent_email = (
        "Subject: URGENT - Statute of Limitations Expiring\n\n"
        "I was injured at my workplace 2 years and 11 months ago. I just learned that the "
        "statute of limitations for personal injury in our state is 3 years. That means I only "
        "have about 30 days to file. Please contact me IMMEDIATELY.\n\n"
        "Maria Garcia, (555) 222-3333, maria.garcia@email.com\n"
        "Injury: Chemical burn at Westfield Chemical plant on May 14, 2023"
    )
    second_email = (
        "Subject: Car Accident - Need Legal Help\n\n"
        "My name is Sarah Johnson and I was in a car accident on February 15, 2026. "
        "The other driver ran a red light. I have $45,000 in medical bills. "
        "Phone: (555) 123-4567."
    )

    try:
        _start_stack(ctx)
        _ensure_proof_org(ctx)
        _issue_factory_token(ctx)
        _commission_build(ctx)
        build = _wait_for_build(ctx)
        bundle_dir = _extract_bundle(ctx, build, args.bundle_dir)
        _write_bundle_env(ctx, bundle_dir)
        _start_employee_bundle(ctx, bundle_dir)

        task_id = _submit_task(ctx, urgent_email)
        _wait_for_task(ctx, task_id)
        brief = _get_brief(ctx, task_id)
        ctx.record("urgent_brief", brief=brief)

        _stop_factory_stack()
        status, _ = _request_text(f"{ctx.employee_url}/api/v1/health", timeout=10)
        if status != 200:
            raise RuntimeError(f"Employee health failed after factory stop: HTTP {status}")
        ctx.record("sovereignty_health", status_code=status)

        second_task = _submit_task(ctx, second_email)
        _wait_for_task(ctx, second_task)
        ctx.record("sovereignty_task", task_id=second_task)
    except Exception as exc:  # noqa: BLE001
        ctx.blockers.append(str(exc))
        print(_report(ctx))
        return 1

    print(_report(ctx))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
