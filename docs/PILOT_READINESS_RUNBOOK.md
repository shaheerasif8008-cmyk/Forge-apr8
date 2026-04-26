# Forge Pilot Readiness Runbook

Last updated: 2026-04-26

This runbook is the Milestone 3 operator path for a first controlled pilot. It
does not claim broad V1 launch readiness. It proves the pilot-facing employee
runtime surfaces, production guard behavior, server-export handoff mechanics,
and explicit degraded integration disclosure.

## Milestone 3 Exit Criteria

- Employee runtime API exposes the daily pilot surfaces: health, auth-protected
  conversation history, task submission, task brief retrieval, corrections,
  memory edits, settings edits, direct behavior commands, document upload,
  daily loop, metrics, and updates.
- Production guard checks prove that protected employee routes reject missing
  credentials.
- Server export proof reaches either `deployed` or `pending_client_action`.
  For server deployments, `pending_client_action` is a successful customer
  handoff state when the bundle is packaged and client installation is required.
- Any degraded integrations are inventoried and disclosed. They are allowed for
  pilot only when the client has explicitly accepted fixture, in-memory, or
  fallback behavior for that capability.
- The operator has a repeatable rollback and support path before a client sees
  the employee.

## Fast Local Pilot Smoke

Run this before any longer Docker or live-infra proof:

```bash
python3 scripts/pilot_readiness_smoke.py --pretty
```

Expected result:

- `overall` is `passed`.
- `production_guards.auth_required` is `true`.
- `production_guards.unauthorized_status` is `401`.
- `degraded_integrations_policy` is
  `allowed_for_pilot_with_disclosure`.
- `degraded integrations` are listed with component IDs, status, and details.

The smoke uses an in-process employee app with auth enabled and exercises the
same API shape used by packaged employees. It intentionally does not require
real Slack, Gmail, Calendar, or cloud credentials.

## Focused Regression Commands

```bash
python3 -m pytest tests/runtime/test_pilot_readiness_smoke.py tests/runtime/test_pilot_readiness_runbook.py -q
python3 -m py_compile scripts/pilot_readiness_smoke.py employee_runtime/core/api.py
```

When touching auth, runtime API, daily loop, memory, or document surfaces, also
run:

```bash
python3 -m pytest tests/runtime/test_employee_api.py tests/runtime/test_runtime_auth.py tests/runtime/test_autonomous_daily_loop.py -q
```

## Server Export Proof

Preflight first. This catches Docker and compose issues without starting the
full factory flow.

```bash
python3 scripts/prove_server_export.py --mode preflight
```

Full proof:

```bash
python3 scripts/prove_server_export.py --mode full
```

Successful full proof means:

- Docker is reachable and compose config is valid.
- A server deployment commission completes through bundle generation.
- The exported bundle is a zip archive with a Docker Compose runtime.
- The exported employee starts independently from Forge.
- Authenticated task calls use `Authorization: Bearer ...`.
- The employee continues serving after the factory is stopped.
- Final server-export state is `pending_client_action` or `deployed`.

Do not mark a failed evaluator run as a packaging failure unless the logs show
bundle creation, image build, or runtime boot failures. If evaluator quality
gates fail, fix the employee behavior and rerun the proof.

## Customer Server Handoff

For a server deployment pilot, give the customer the server bundle and the
installation instructions generated inside it. The operator must verify these
fields before handoff:

- `EMPLOYEE_API_KEY` is present in the bundle `.env` or customer secret store.
- Public URLs or local ports match the customer's network plan.
- No Forge factory URL is required for runtime task execution.
- Any required external provider credentials are documented by name, not copied
  into the runbook.

Customer install flow:

```bash
unzip forge-employee-*-server-bundle.zip
cd forge-employee-*-server-bundle
cp .env.example .env
# Set EMPLOYEE_API_KEY and provider credentials.
docker compose up -d
curl http://localhost:8000/api/v1/health
curl -H "Authorization: Bearer $EMPLOYEE_API_KEY" http://localhost:8000/api/v1/meta
```

Shutdown and rollback:

```bash
docker compose down
docker compose logs --tail=200
```

If the employee package fails after handoff, collect compose logs, the bundle
metadata file, and the exact task/correction payload that reproduced the issue.
Do not request client raw data unless it is necessary and approved.

## Production Guard Policy

Before a real external pilot, set strict provider behavior in staging:

```bash
export FORGE_STRICT_PROVIDERS=true
```

Required guards:

- Factory portal and API use Clerk-backed sessions and organization context.
- Employee app/runtime requires `EMPLOYEE_API_KEY` or the deployed equivalent.
- Tool actions pass through ToolBroker for permission, audit, and credential
  checks.
- Production startup must fail or report not-ready when mandatory credentials
  are absent.
- Degraded integrations are visible in readiness output and customer-facing
  pilot notes.

## Degraded Integration Rules

`degraded integrations` means any runtime capability using fixture, in-memory,
fallback, or simulated behavior instead of the production provider.

Allowed for internal pilot:

- Fixture email or messaging when the test objective is runtime UX and workflow
  behavior.
- In-memory storage when validating local API shape and operator flow.
- Parser fallback when validating document upload surface without native
  extraction binaries.

Not allowed for external pilot unless disclosed in writing:

- Fake send/receive behavior for Gmail, Slack, Teams, or Calendar.
- Silent fallback from real provider failure to fixture behavior.
- Any simulated approval, audit, memory, or task completion path presented as
  production evidence.

## Operator Checklist

1. Run the local pilot smoke and save the JSON output.
2. Run focused regression tests.
3. Run server export preflight.
4. Run full server export proof when Docker, disk, and credentials are ready.
5. Review evaluator failures separately from packaging/deployment failures.
6. Confirm auth guards on factory and employee surfaces.
7. Confirm degraded integration inventory and customer disclosure.
8. Hand off the server bundle only after health and authenticated meta checks
   pass.
9. Track remaining broad-launch gaps separately from pilot acceptance.

## Still Outside Milestone 3

- Signed Electron installers for all platforms.
- Hosted Railway production deployment proof.
- Two-week internal pilot evidence.
- Real Gmail, Slack/Teams, and Calendar processing with client accounts.
- Federated learning and marketplace lifecycle proof.
- Formal SOC 2 certification.
