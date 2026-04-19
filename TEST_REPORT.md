# Forge Test Report

Run date: 2026-04-19
Workspace: `/Users/shaheer/Downloads/Forge-Apr8`

## Summary Table

| Phase | Status | Duration | LLM Cost | Bugs Found |
| --- | --- | --- | --- | --- |
| 0 Env Bring-Up | ❌ failed | ~4m | $0.00 | 4 |
| 1 Unit Tests | ❌ failed | ~1m | $0.00 | 36 |
| 2 API Smoke | skipped | 0m | $0.00 | 0 |
| 3 Component Library | skipped | 0m | $0.00 | 0 |
| 4 Deliberation Council | skipped | 0m | $0.00 | 0 |
| 5 Full E2E Pipeline | skipped | 0m | $0.00 | 0 |
| 6 UI Walkthrough | skipped | 0m | $0.00 | 0 |
| 7 Chaos (optional) | skipped | 0m | $0.00 | 0 |

## Phase 0 — Environment Bring-Up

Status: failed

### Environment Notes

- `docker` was not on the Codex shell `PATH`, but the CLI exists at `/usr/local/bin/docker` and Docker Desktop is running.
- `.env` contains `OPENAI_API_KEY` and `OPENROUTER_API_KEY`.
- `ANTHROPIC_API_KEY` is still unset.

### Commands Run

```bash
/usr/local/bin/docker version
/usr/local/bin/docker compose version
printf 'ANTHROPIC_API_KEY set: %s\n' "${ANTHROPIC_API_KEY:+yes}"
printf 'OPENAI_API_KEY set: %s\n' "${OPENAI_API_KEY:+yes}"
printf 'OPENROUTER_API_KEY set: %s\n' "${OPENROUTER_API_KEY:+yes}"
docker compose up -d postgres redis minio opa
docker compose ps -a
curl -sf http://localhost:5432 >/dev/null || echo "postgres TCP check"
docker compose exec -T postgres pg_isready -U forge -d forge
docker compose exec -T redis redis-cli ping
curl -sf http://localhost:9000/minio/health/live
curl -sf http://localhost:8181/health
docker compose logs --tail=100 opa
docker compose up -d factory pipeline-worker
curl -sf http://localhost:8000/api/v1/health
docker compose exec -T postgres psql -U forge -d forge -P pager=off -c "\dt"
docker compose exec -T postgres psql -U forge -d forge -P pager=off -c "SELECT extname FROM pg_extension ORDER BY extname;"
docker compose exec -T minio sh -lc 'mc alias set local http://localhost:9000 minioadmin minioadmin >/dev/null 2>&1; if mc ls local/forge-packages >/dev/null 2>&1; then echo exists; else mc mb local/forge-packages >/dev/null && echo created; fi'
docker compose run --rm factory alembic current
```

### Service State

`docker compose ps -a` after bring-up:

```text
NAME                    IMAGE                              COMMAND                  SERVICE    CREATED       STATUS                      PORTS
forge-apr8-minio-1      minio/minio:latest                 "/usr/bin/docker-ent…"   minio      3 hours ago   Up 3 hours (healthy)        0.0.0.0:9000-9001->9000-9001/tcp, [::]:9000-9001->9000-9001/tcp
forge-apr8-opa-1        openpolicyagent/opa:latest-envoy   "/opa run --server -…"   opa        2 hours ago   Exited (1) 54 seconds ago
forge-apr8-postgres-1   pgvector/pgvector:pg16             "docker-entrypoint.s…"   postgres   3 hours ago   Up 3 hours (healthy)        0.0.0.0:5432->5432/tcp, [::]:5432->5432/tcp
forge-apr8-redis-1      redis:7-alpine                     "docker-entrypoint.s…"   redis      3 hours ago   Up 3 hours (healthy)        0.0.0.0:6379->6379/tcp, [::]:6379->6379/tcp
```

### Health Checks

- Postgres TCP probe: `postgres TCP check`
- Postgres readiness: `/var/run/postgresql:5432 - accepting connections`
- Redis readiness: `PONG`
- MinIO health endpoint responded successfully
- OPA health endpoint failed
- Factory health endpoint responded once during startup:

```json
{"status":"ok","service":"forge-factory","version":"0.2.0"}
```

That response was not stable. The container then exited and `pipeline-worker` could not stay up because its `factory` dependency failed to start.

### OPA Failure

`docker compose logs --tail=100 opa`:

```text
opa-1  | error: load error: 1 error occurred during loading: /policies/legal.rego:18: rego_parse_error: unexpected plus token
opa-1  | 	violations := [v | v := deny_legal_advice[_]] ++ [v | v := deny_conflict[_]]
opa-1  | 	                                               ^
```

This means compliance policy serving is down from startup.

### Factory Failure

`docker compose logs --tail=200 factory pipeline-worker` showed the factory container exiting on import:

```text
ImportError: email-validator is not installed, run `pip install 'pydantic[email]'`
```

The failure occurs while importing `factory.models.client.ClientOrg`, which uses Pydantic email field validation. This also breaks Alembic.

### Schema State

`psql -c "\dt"`:

```text
               List of relations
 Schema |         Name          | Type  | Owner
--------+-----------------------+-------+-------
 public | audit_events          | table | forge
 public | blueprints            | table | forge
 public | builds                | table | forge
 public | client_orgs           | table | forge
 public | clients               | table | forge
 public | conversations         | table | forge
 public | deployments           | table | forge
 public | employee_requirements | table | forge
 public | knowledge_chunks      | table | forge
 public | messages              | table | forge
 public | monitoring_events     | table | forge
 public | operational_memories  | table | forge
 public | performance_metrics   | table | forge
 public | reasoning_records     | table | forge
(14 rows)
```

Extension check:

```text
 extname
---------
 plpgsql
 vector
(2 rows)
```

### MinIO Bucket

The required bucket was missing initially. I created it manually:

```text
created
```

### Alembic Current

`docker compose run --rm factory alembic current` failed with the same missing dependency:

```text
ImportError: email-validator is not installed, run `pip install 'pydantic[email]'`
```

### Findings

1. `component_library/quality/policies/legal.rego` contains invalid Rego syntax at line 18, which prevents OPA from starting.
2. The factory image is missing `email-validator`, so the factory API cannot boot reliably and Alembic cannot run.
3. `forge-packages` did not exist in MinIO and had to be created manually.
4. `ANTHROPIC_API_KEY` is still absent, which would block full LLM-backed coverage even if the app stack were healthy.

## Phase 1 — Unit Test Sweep

Status: failed

### Plan Deviation Required to Run Tests

The plan’s command:

```bash
docker compose exec factory pytest tests/ -v --tb=short --junit-xml=/app/test_results.xml
```

could not run because the factory image does not include `pytest`.

Observed first attempt:

```text
Error response from daemon: failed to create task for container: failed to create shim task: OCI runtime create failed: runc create failed: unable to start container process: error during container init: exec: "pytest": executable file not found in $PATH
```

To continue the test plan without changing repository code, I used a disposable one-off container and installed test-only dependencies ephemerally:

```bash
docker compose run --rm -v "$PWD:/workspace" factory sh -lc \
  "pip install -e '.[dev]' email-validator >/tmp/pip.log 2>&1 && \
   pytest tests/ -v --tb=short --junit-xml=/workspace/test_results.xml"
```

This produced [test_results.xml](/Users/shaheer/Downloads/Forge-Apr8/test_results.xml).

### Overall Result

- Total collected: 205
- Passed: 169
- Failed: 30
- Errors: 6
- Pass rate: 82.4%
- Wall time: 32.96s

Per the plan, this is below the required 90% pass floor, so execution stops here.

### Pass/Fail Counts Per Group

| Group | Total | Passed | Failed | Errors | Skipped | Time |
| --- | --- | --- | --- | --- | --- | --- |
| `tests/components/` | 114 | 114 | 0 | 0 | 0 | 0.50s |
| `tests/factory/` | 60 | 46 | 8 | 6 | 0 | 24.93s |
| `tests/runtime/` | 22 | 9 | 13 | 0 | 0 | 0.63s |
| `tests/integration/` | 6 | 0 | 6 | 0 | 0 | 0.03s |
| `tests/observability/` | 3 | 0 | 3 | 0 | 0 | 0.01s |

No individual test exceeded 30 seconds.

### Root-Cause Summary

1. The factory image lacks `pytest`, so the test sweep cannot run as written.
2. The image also lacks `email-validator`, which blocks normal app startup and migration checks.
3. The repository contains large packaged Electron output under `portal/employee_app/dist`:

```text
728M	portal/employee_app/dist
1.7M	portal/employee_app/out
```

Example committed artifact:

```text
portal/employee_app/dist/${env.FORGE_EMPLOYEE_NAME}-0.1.0-arm64.dmg
```

4. Once assembler and runtime tests touch those artifacts, the container hits `OSError: [Errno 28] No space left on device`, which cascades across factory, runtime, integration, and observability failures.
5. Docker storage pressure is elevated:

```text
TYPE            TOTAL     ACTIVE    SIZE      RECLAIMABLE
Images          22        19        22.86GB   999.2MB (4%)
Containers      48        8         4.616MB   860.2kB (18%)
Local Volumes   5         5         1.161GB   0B (0%)
Build Cache     97        0         16.26GB   16.05GB
```

### Full List of Failing Tests

- `tests/factory/test_pipeline/test_assembler.py::test_assembler_creates_build_directory`
  `shutil.Error` while copying `portal/employee_app/dist/...`; root cause is `Errno 28` from the oversized committed desktop build artifacts.
- `tests/factory/test_pipeline/test_deployer_integrations.py::test_pipeline_rolls_back_on_activate_failure`
  `OSError: [Errno 28] No space left on device` while logging deploy failure.
- `tests/factory/test_pipeline/test_deployer_providers.py::test_provisioner_dispatches_server_export`
  `OSError: [Errno 28] No space left on device`.
- `tests/factory/test_pipeline/test_deployer_providers.py::test_provisioner_dispatches_local`
  `OSError: [Errno 28] No space left on device`.
- `tests/factory/test_pipeline/test_evaluator.py::test_evaluator_runs_black_box_suites`
  `OSError: [Errno 28] No space left on device`.
- `tests/factory/test_pipeline/test_full_pipeline.py::test_full_pipeline_deploys_on_success`
  `OSError: [Errno 28] No space left on device`.
- `tests/factory/test_pipeline/test_generator_llm.py::test_generator_retries_until_generated_tests_pass`
  Fixture setup error: pytest could not create temp directories under `/tmp/pytest-of-root/...` because the container ran out of space.
- `tests/factory/test_pipeline/test_generator_llm.py::test_generator_fails_after_max_iterations`
  Same temp-directory creation failure under `/tmp`.
- `tests/factory/test_pipeline/test_generator_llm.py::test_cost_math_uses_real_usage_counts`
  Same temp-directory creation failure under `/tmp`.
- `tests/factory/test_pipeline/test_packager.py::test_packager_builds_and_records_artifact`
  Same temp-directory creation failure under `/tmp`.
- `tests/factory/test_pipeline/test_packager.py::test_packager_handles_docker_failure`
  Same temp-directory creation failure under `/tmp`.
- `tests/factory/test_pipeline/test_packager_desktop.py::test_packager_builds_desktop_installers_when_requested`
  Same temp-directory creation failure under `/tmp`.
- `tests/factory/test_pipeline/test_pipeline_worker.py::test_pipeline_completes`
  `OSError: [Errno 28] No space left on device`.
- `tests/factory/test_pipeline/test_pipeline_worker.py::test_pipeline_stops_after_generation_failure`
  `OSError: [Errno 28] No space left on device`.
- `tests/integration/test_legal_intake_workflow.py::test_legal_intake_workflow[...]qualified` for `CLEAR_QUALIFIED`
  `OSError: [Errno 28] No space left on device`.
- `tests/integration/test_legal_intake_workflow.py::test_legal_intake_workflow[...]not_qualified` for `CLEAR_UNQUALIFIED`
  `OSError: [Errno 28] No space left on device`.
- `tests/integration/test_legal_intake_workflow.py::test_legal_intake_workflow[...]needs_review` for `AMBIGUOUS`
  `OSError: [Errno 28] No space left on device`.
- `tests/integration/test_legal_intake_workflow.py::test_legal_intake_workflow[...]qualified` for `POTENTIAL_CONFLICT`
  `OSError: [Errno 28] No space left on device`.
- `tests/integration/test_legal_intake_workflow.py::test_legal_intake_workflow[...]qualified` for `URGENT`
  `OSError: [Errno 28] No space left on device`.
- `tests/integration/test_legal_intake_workflow.py::test_legal_intake_workflow_uses_router_backed_components`
  `OSError: [Errno 28] No space left on device`.
- `tests/observability/test_langfuse_integration.py::test_langfuse_disabled_is_noop`
  `OSError: [Errno 28] No space left on device`.
- `tests/observability/test_langfuse_integration.py::test_langfuse_records_model_generations_and_engine_spans`
  `OSError: [Errno 28] No space left on device`.
- `tests/observability/test_langfuse_integration.py::test_langfuse_records_pipeline_spans`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_autonomous_daily_loop.py::test_hosted_employee_daily_loop_executes_real_workflow`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_behavior_rules.py::test_behavior_rule_precedence_prefers_direct_commands`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_behavior_rules.py::test_daily_loop_respects_quiet_hours_rules`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_conversation_persistence.py::test_chat_history_survives_service_reinitialization`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_conversation_persistence.py::test_pending_approvals_recover_after_restart`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_conversation_persistence.py::test_corrections_and_daily_loop_messages_persist_after_restart`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_conversation_persistence.py::test_websocket_chat_persists_messages_in_order`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_employee_api.py::test_employee_api_task_flow`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_employee_api.py::test_employee_api_memory_ops_and_metrics_dashboard`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_employee_api.py::test_employee_api_knowledge_document_upload`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_executive_assistant_api.py::test_executive_assistant_runtime_flow`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_executive_assistant_api.py::test_executive_assistant_novel_situation_proposes_options`
  `OSError: [Errno 28] No space left on device`.
- `tests/runtime/test_executive_assistant_api.py::test_executive_assistant_correction_path_learns_and_escalates_repeats`
  `OSError: [Errno 28] No space left on device`.

## Phase 2 — Factory API Smoke Test

Skipped because the plan says to stop and investigate when Phase 1 falls below 90% pass rate. The factory API also does not start cleanly due the missing `email-validator` dependency.

## Phase 3 — Component Library Production Readiness

Skipped because execution stopped after Phase 1 and the factory stack is not healthy.

## Phase 4 — Deliberation Council Isolated Test

Skipped because execution stopped after Phase 1. `ANTHROPIC_API_KEY` also remains unset, which reduces intended coverage for LLM-backed phases.

## Phase 5 — Full End-to-End Pipeline Run

Skipped because execution stopped after Phase 1 and the factory/runtime environment is not healthy enough to produce a meaningful full build result.

## Phase 6 — UI End-to-End via Computer Use

Skipped because the backend stack did not reach a stable healthy state.

## Phase 7 — Chaos & Edge Cases

Skipped because Phase 5 was not reached.

## Confidence Summary

- Factory runtime surface: 2/10. Postgres, Redis, MinIO, and schema setup exist, but OPA is down, the factory container cannot boot reliably, Alembic cannot run, and factory pipeline tests are failing under disk pressure.
- Evaluator ephemeral containers: 1/10. The evaluator path was only exercised indirectly through failing unit tests and did not reach a trustworthy live packaged-container run.
- Deployed employee containers: 1/10. Runtime, integration, and employee API tests collapse under `Errno 28`, and no stable deployed employee was produced.

## Blocking Bugs

- `component_library/quality/policies/legal.rego:18` has invalid Rego syntax, so OPA never starts.
- The factory image is missing `email-validator`, which breaks factory startup and Alembic.
- The factory image is missing `pytest`, so the Phase 1 command in the test plan cannot run as written.
- `portal/employee_app/dist` contains large packaged desktop artifacts, including a `.dmg`, and assembler copies them into build directories, exhausting container disk and causing widespread `Errno 28` failures.
- `ANTHROPIC_API_KEY` is still unset, so intended Anthropic-backed coverage remains incomplete even after startup issues are fixed.

## Non-Blocking Issues

- The Codex shell `PATH` does not include `/usr/local/bin`, so `docker` is only reachable by absolute path unless the shell environment is adjusted.
- The `forge-packages` bucket was absent in MinIO and required manual creation.
