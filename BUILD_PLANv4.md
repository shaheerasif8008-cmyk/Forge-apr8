# Codex Build Plan — Forge V1 Completion

> Execution plan for completing Forge from its current state to a demoable V1. Written for Codex CLI sessions. Drop this file in the repo root alongside `AGENTS.md`, `CLAUDE.md`, and `DECISIONS.md`.

---

## 1. Current State (April 2026)

### What works
- **Factory pipeline orchestration.** Celery worker in `factory/workers/pipeline_worker.py` correctly sequences Architect → Assembler → Generator → Packager → Evaluator → self-correction → Deployer → activation with Postgres persistence between stages.
- **Packager builds a real Docker image.** `factory/pipeline/builder/packager.py` shells out to `docker build` and saves a tarball artifact.
- **Evaluator runs real containers.** `container_runner.py` starts the built image, hits `/health`, runs functional/security/behavioral test suites, cleans up.
- **Employee Engine.** `employee_runtime/core/engine.py` is a working LangGraph StateGraph runner with streaming support and a workflow registry (legal_intake, executive_assistant).
- **Pulse Engine.** `employee_runtime/modules/pulse_engine.py` — 410 lines, real implementation.
- **BehaviorManager.** 211 lines, real implementation of direct commands + portal rules + adaptive learning.
- **Four real work components:** text_processor (295), document_analyzer (224), draft_generator (134), workflow_executor (113).
- **Audit system.** 160 lines, real append-only logging.

### What's stubbed, shallow, or missing
| Component | Status | Gap |
| --- | --- | --- |
| `factory/pipeline/builder/generator.py` | Writes placeholder `.py` files | No LLM code generation, no self-correcting loop |
| `factory/pipeline/builder/packager.py` | Only builds the Python backend | No `npm run build`, no `electron-builder`, no code signing |
| `factory/pipeline/analyst/conversation.py` | Keyword-based routing | Not LLM-driven |
| `factory/pipeline/architect/component_selector.py` | Hardcoded baseline lists | Not LLM-driven |
| `factory/pipeline/architect/gap_analyzer.py` | Unknown depth | Likely rule-based |
| `factory/pipeline/deployer/provisioner.py` | Local Docker only | No Railway/AWS/client-cloud, no Composio OAuth, no rollback |
| `employee_runtime/modules/deliberation.py` | 10-line stub | The adversarial Council doesn't exist |
| `component_library/quality/adversarial_review.py` | Keyword match | Not the real Deliberation Council |
| `component_library/quality/autonomy_manager.py` | Single threshold | Not confidence-gated autonomy logic |
| `component_library/quality/explainability.py` | Likely shallow | Not a real reasoning-record generator |
| `component_library/quality/compliance_rules.py` | Likely shallow | No OPA integration |
| `component_library/work/research_engine.py` | 24-line stub | Marked stub in `status.py` |
| `component_library/work/data_analyzer.py` | 24-line stub | Marked "reference" |
| `component_library/work/monitor_scanner.py` | 24-line stub | Marked stub |
| `component_library/tools/search_tool.py` | Stub | Needs Tavily integration |
| `component_library/tools/file_storage_tool.py` | Stub | Needs S3/MinIO |
| `component_library/tools/document_ingestion.py` | Stub | Needs Unstructured |
| `component_library/tools/custom_api_tool.py` | Stub | Generic HTTP client |
| `component_library/data/knowledge_base.py` | "Reference" | Needs pgvector integration |
| `portal/employee_app/components/SidebarPanels.tsx` | Renders raw JSON | Needs real rich UI per panel |
| `portal/factory_portal/` | 145 lines | Commission flow, build tracking, roster mostly skeleton |
| LangFuse integration | Not wired | No LLM tracing |
| Guardrails AI integration | Not wired | Input/output safety relies on custom code |
| DeepEval integration | Not wired | Evaluator tests are hand-rolled |
| OPA integration | Not wired | Compliance rules not enforced via policy engine |

### Headline number
~11,000 lines of code in place. Scaffolding ~70% complete. Depth-inside-modules ~35% complete. The architecture decisions are all sound — the gap is implementation depth, not structural rework.

---

## 2. How to Use This Plan

### For Codex
Each **work package (WP)** is scoped to a single Codex session. The session prompt is pre-written — copy it verbatim into Codex. Each WP lists the exact files Codex should touch, the acceptance criteria it must satisfy, and tests to update or add. Follow package order within a track; across tracks, run in parallel.

### Rules Codex must follow across every session
1. **Never delete or simplify the Deliberation module stub warning in `employee_runtime/modules/deliberation.py` until the real implementation lands in WP-C1.**
2. **Every new LLM call must go through `component_library/models/litellm_router.py` or `anthropic_provider.py`** — not direct SDK calls.
3. **Every new Celery task must persist intermediate state to Postgres via `factory/persistence.py`** — the pipeline must resume from any stage if a worker dies.
4. **Every new component must implement `BaseComponent`** (`component_library/interfaces.py`) and register via `@register(...)`.
5. **Every new component must register its status in `component_library/status.py`** (`stub` / `reference` / `production`). `production` means: integration-tested end-to-end, ships to clients.
6. **All new async code uses the project's `structlog` logger** with contextual kwargs.
7. **Tests are mandatory** — a WP is not complete until the specified tests pass.

---

## 3. Execution Tracks

Run these two tracks in parallel.

**Track 1 — Backend / Factory (sequential):** A → B → C → D
**Track 2 — Frontend / Portal (sequential):** E → F

Track 1 is the critical path. Track 2 can start immediately and run alongside.

---

# TRACK 1 — BACKEND / FACTORY

## Phase A — Complete the Factory Output

Goal: make the Builder produce a real, end-to-end shippable employee package (backend + frontend + Dockerized + optionally desktop installer).

---

### WP-A1 — Packager: Add Frontend Build Step

**Why:** Today the Packager builds only the Python backend into a container. The employee ships without its UI. The Next.js frontend must be built and bundled into the container so the employee can serve its own app.

**Files to modify:**
- `factory/pipeline/builder/packager.py`
- `factory/pipeline/builder/assembler.py` (inject employee config into frontend)
- `factory/pipeline/builder/dockerfile_generator.py`
- `portal/employee_app/next.config.js` (support static export)
- `portal/employee_app/app/config.ts` (new — runtime config injection)

**Acceptance criteria:**
- The Assembler copies `portal/employee_app/` into `<build_dir>/portal/employee_app/` and writes a customized `config.ts` containing employee_id, employee_name, employee_role, enabled_sidebar_panels (derived from the Blueprint).
- The Packager runs `npm ci` and `npm run build` (via `subprocess.run`) inside `<build_dir>/portal/employee_app/` before `docker build`.
- The generated Dockerfile uses a multi-stage build: stage 1 builds Node/Next.js, stage 2 runs Python and serves both the FastAPI API and the compiled frontend via FastAPI's `StaticFiles` mount at `/`.
- On `docker run`, hitting `http://<host>:<port>/` returns the compiled frontend HTML and hitting `/api/v1/health` returns `{"status": "ok"}`.
- New integration test `tests/factory/test_pipeline/test_packager_frontend.py` runs a full assemble+package and asserts the built image serves both frontend and API.

**Codex prompt:**
```
Modify the Forge Packager to include the Next.js frontend build step.

Read the files listed below to understand the current implementation:
- factory/pipeline/builder/assembler.py
- factory/pipeline/builder/packager.py
- factory/pipeline/builder/dockerfile_generator.py
- portal/employee_app/next.config.js
- portal/employee_app/package.json

Changes required:
1. In assembler.py, after copying portal/employee_app into the build directory,
   write a portal/employee_app/app/config.ts file with injected employee identity
   from the EmployeeBlueprint (employee_id, name, role, enabled_panels).
2. In next.config.js, enable static export (output: 'export') so the build
   produces static HTML/JS/CSS at portal/employee_app/out/.
3. In packager.py, BEFORE the docker build step, run:
     subprocess.run(['npm', 'ci'], cwd=<build_dir>/portal/employee_app, ...)
     subprocess.run(['npm', 'run', 'build'], cwd=<build_dir>/portal/employee_app, ...)
   Fail the build with a proper BuildLog entry if either fails.
4. In dockerfile_generator.py, emit a multi-stage Dockerfile:
     Stage 1 (node:20-alpine): cd portal/employee_app && npm ci && npm run build
     Stage 2 (python:3.12-slim): copy backend + copy --from=stage1 /app/portal/employee_app/out
     to /app/static. Install Python deps, expose 8000, run uvicorn.
5. In employee_runtime/core/api.py, mount the static directory at "/" using
   fastapi.staticfiles.StaticFiles, and move API routes under /api/v1/*.
6. Add integration test tests/factory/test_pipeline/test_packager_frontend.py
   that runs the full pipeline on a minimal legal_intake blueprint and asserts
   the produced image responds on both / and /api/v1/health when run.

Run: pytest tests/factory/test_pipeline/test_packager_frontend.py -v
```

---

### WP-A2 — Packager: Add Electron Desktop Build

**Why:** Desktop delivery is one of the three advertised delivery formats. Without `electron-builder` wired into the pipeline, the factory cannot produce `.dmg` / `.exe` / `.AppImage` installers.

**Files to modify:**
- `factory/pipeline/builder/packager.py`
- `portal/employee_app/electron-builder.yml` (new)
- `portal/employee_app/electron/main.js`
- `factory/models/build.py` (add `desktop_installer` to BuildArtifact types)

**Acceptance criteria:**
- Packager reads `deployment_format` from the Blueprint. When `desktop` or `hybrid`, runs `npx electron-builder --mac --win --linux` inside the build dir.
- Produced installers are uploaded to artifact storage via `artifact_store.py` and referenced in `build.artifacts`.
- If code-signing certificates are available via env vars (`CSC_LINK`, `CSC_KEY_PASSWORD`), the Packager passes them through; otherwise it logs a warning and produces unsigned installers.
- Electron's `main.js` loads the local frontend URL (when backend runs locally) or the deployed URL (when backend is cloud-connected) based on a `FORGE_BACKEND_URL` env var baked into the installer at build time.
- New test `tests/factory/test_pipeline/test_packager_desktop.py` runs the pipeline with `deployment_format=desktop` and asserts at least one installer artifact is produced (can skip the heavy builds in CI via env flag, but test the invocation logic).

**Codex prompt:**
```
Extend the Forge Packager to produce Electron desktop installers.

Current state: factory/pipeline/builder/packager.py only runs docker build.
Requirement: when the blueprint's deployment_format is "desktop" or "hybrid",
ALSO run electron-builder and upload the resulting installers as
BuildArtifacts.

Steps:
1. Create portal/employee_app/electron-builder.yml with appId=com.cognisia.forge.<employee_id_placeholder>,
   productName from config, targets for mac (dmg), win (nsis), linux (AppImage).
2. Update portal/employee_app/electron/main.js to read FORGE_BACKEND_URL at
   runtime (via preload bridge) and load that URL instead of a hardcoded path.
   Fall back to the bundled static export if FORGE_BACKEND_URL is empty.
3. In packager.py, after the frontend build completes and BEFORE docker build,
   check blueprint.deployment_format. If it includes "desktop":
     subprocess.run(['npx', 'electron-builder', '--mac', '--win', '--linux',
                     '--publish=never'], cwd=<build_dir>/portal/employee_app)
   Timeout=1200. Pass through CSC_LINK and CSC_KEY_PASSWORD env vars if set.
4. For every produced installer (*.dmg, *.exe, *.AppImage), call
   artifact_store.store_file(path, build.id, artifact_type='desktop_installer').
5. Add "desktop_installer" as a valid BuildArtifact.artifact_type in
   factory/models/build.py.
6. Write tests/factory/test_pipeline/test_packager_desktop.py. Use a
   FORGE_SKIP_HEAVY_BUILDS=1 env gate so CI can mock the subprocess calls
   while asserting they would be invoked with correct args.

Run: pytest tests/factory/test_pipeline/test_packager_desktop.py -v
```

---

### WP-A3 — Generator: Real LLM Code Generation + Self-Correcting Loop

**Why:** Today the Generator writes literal placeholder files. The whole point of the factory's differentiation over pure assembly is that it can generate custom modules for gaps the library doesn't cover, with a self-correcting test loop.

**Files to modify:**
- `factory/pipeline/builder/generator.py` (major rewrite)
- `factory/pipeline/builder/prompts/` (new directory)
- `factory/pipeline/builder/prompts/custom_module_template.md` (new)
- `factory/pipeline/builder/prompts/test_generation_template.md` (new)
- `factory/pipeline/evaluator/self_correction.py` (wire into Generator)
- `factory/config.py` (add `MAX_GENERATION_ITERATIONS=5`, `GENERATOR_MODEL`)

**Acceptance criteria:**
- For each `CustomCodeSpec` in the Blueprint, the Generator: (1) calls Claude via `anthropic_provider` with a structured prompt containing the component interface, the spec description, the surrounding workflow context, and examples from the library; (2) writes the generated `.py` module to `<build_dir>/generated/`; (3) generates a `test_<spec_name>.py` file with pytest test cases covering the spec's described behaviors; (4) runs the generated tests via subprocess `pytest`; (5) if tests fail, feeds stdout/stderr back to Claude with the current code and asks for a fix; (6) repeats up to `MAX_GENERATION_ITERATIONS` (5).
- Every generated module must import from and extend `BaseComponent` (or `WorkCapability` / etc.). Every generated module is auto-registered via `@register(...)`.
- The Generator logs each iteration to `BuildLog` with the full prompt and response (truncated to 4KB).
- If after 5 iterations the tests still fail, the Build is marked `FAILED` with a clear error log and does not proceed to Evaluator.
- Token cost per generation is tracked in `build.metadata['generation_cost_usd']`.
- New test `tests/factory/test_pipeline/test_generator_llm.py` uses a mocked Anthropic client to verify: correct prompt construction, the iteration loop, failure after N iterations, success when tests pass.

**Codex prompt:**
```
Replace the stub Generator in factory/pipeline/builder/generator.py with a
real LLM-driven code-generation loop with self-correction.

Context files to read first:
- factory/pipeline/builder/generator.py (current stub)
- factory/models/blueprint.py (CustomCodeSpec shape)
- component_library/interfaces.py (BaseComponent contract)
- component_library/work/text_processor.py (example real component to use as few-shot)
- component_library/models/anthropic_provider.py (how to call Claude)

Implementation:
1. Create factory/pipeline/builder/prompts/custom_module_template.md with a
   structured prompt that takes: component interface, spec description,
   existing-component example, workflow position. The prompt must instruct
   Claude to produce ONLY Python code in a single code block.
2. Create factory/pipeline/builder/prompts/test_generation_template.md for
   generating pytest test cases from the same spec.
3. Rewrite generator.py:
   - For each CustomCodeSpec, render the module prompt and call
     anthropic_provider.generate(model='claude-3.5-sonnet', ...).
   - Parse the code block, write to <build_dir>/generated/<spec_name>.py.
   - Render the test prompt, call Claude again, write the test file.
   - Run: subprocess.run(['pytest', '<test_file>', '-x', '-q'], cwd=<build_dir>).
   - If returncode != 0, build a "fix prompt" that includes the current code,
     the test file, and the pytest output, and ask Claude to return a fixed
     version. Re-run tests. Repeat up to MAX_GENERATION_ITERATIONS (from
     factory/config.py, default 5).
   - Append a BuildLog entry per iteration with prompt_hash, response_length,
     test_result, iteration_number.
   - Track cumulative token cost in build.metadata['generation_cost_usd'].
4. If iterations exhausted without passing tests, set build.status = FAILED
   with a clear error BuildLog; do NOT proceed.
5. Update factory/workers/pipeline_worker.py: if Generator fails, skip
   Packager and Evaluator and persist the failed build.
6. Add constants to factory/config.py: MAX_GENERATION_ITERATIONS=5,
   GENERATOR_MODEL='claude-3.5-sonnet', GENERATOR_TEST_TIMEOUT=60.
7. Write tests/factory/test_pipeline/test_generator_llm.py with a mocked
   Anthropic client covering: success path, success after 2 iterations,
   failure after 5 iterations, token cost tracking, failed-build persistence.

Run: pytest tests/factory/test_pipeline/test_generator_llm.py -v
```

---

### WP-A4 — Deployer: Connector (Composio OAuth) + Rollback

**Why:** Today the Deployer activates an employee but doesn't wire up its integrations. A legal intake employee that can't read email isn't useful. Also: if deployment fails partway, there's no rollback.

**Files to modify:**
- `factory/pipeline/deployer/connector.py` (new)
- `factory/pipeline/deployer/rollback.py` (new)
- `factory/pipeline/deployer/activator.py` (call connector before activation)
- `factory/workers/pipeline_worker.py` (call rollback on deployment failure)
- `factory/api/deployments.py` (expose OAuth callback endpoint)
- `factory/models/deployment.py` (add `integrations: list[IntegrationStatus]`)

**Acceptance criteria:**
- `Connector.connect(deployment)` reads required tools from the Blueprint (email, calendar, slack, crm), kicks off a Composio OAuth flow per tool, stores the resulting connection_id in `deployment.integrations`, and returns a list of OAuth URLs the client must visit.
- `GET /api/v1/deployments/{id}/integrations/urls` returns the pending OAuth URLs.
- `POST /api/v1/deployments/{id}/integrations/callback` receives Composio webhook callbacks and marks integrations as `connected`.
- `Activator.activate(deployment)` now waits for all integrations to be `connected` before transitioning to `ACTIVE`; times out after 1 hour with status `PENDING_CLIENT_ACTION`.
- `Rollback.rollback(deployment)` stops the container, deletes the connection credentials, removes the deployment record, and emits a MonitoringEvent.
- `pipeline_worker.py` calls `rollback` if `provision` or `activate` fails.
- New test `tests/factory/test_pipeline/test_deployer_integrations.py` covers the full flow with mocked Composio.

**Codex prompt:**
```
Add Composio OAuth connector and rollback to the Forge Deployer.

Context:
- factory/pipeline/deployer/provisioner.py and activator.py (current state)
- factory/models/deployment.py (Deployment model to extend)
- factory/models/blueprint.py (how to read required tools)

Install: composio-core, composio-langgraph

Steps:
1. Extend factory/models/deployment.py with:
     class IntegrationStatus(BaseModel):
         tool_id: str
         provider: str   # "gmail" | "outlook" | "slack" | "hubspot" | ...
         composio_connection_id: str | None = None
         oauth_url: str | None = None
         status: Literal["pending", "connected", "failed"]
   Add `integrations: list[IntegrationStatus] = []` to Deployment.
2. Create factory/pipeline/deployer/connector.py with async connect(
     deployment, blueprint) -> Deployment. For each selected tool component
     in the blueprint, call Composio to initiate an OAuth flow, store the
     connection_id and oauth_url, append IntegrationStatus entries with
     status="pending".
3. Create factory/pipeline/deployer/rollback.py with async rollback(
     deployment). Stop container via container_runner.stop_container,
     delete Composio connections, mark deployment.status="ROLLED_BACK",
     emit MonitoringEvent.
4. Update activator.py: after health check passes, poll Composio every
   30s (for up to 1 hour) to confirm all integrations are connected. If
   timeout, set deployment.status="PENDING_CLIENT_ACTION" and return.
5. Update factory/api/deployments.py:
     GET /api/v1/deployments/{id}/integrations/urls
         returns [{"tool_id", "oauth_url"}] for pending integrations
     POST /api/v1/deployments/{id}/integrations/callback
         receives Composio webhook, updates IntegrationStatus to "connected"
6. Update factory/workers/pipeline_worker.py: wrap provision+connect+activate
   in a try/except; on any failure, call rollback and persist.
7. Write tests/factory/test_pipeline/test_deployer_integrations.py with
   mocked Composio SDK covering: successful connect+activate, timeout,
   rollback-on-failure, OAuth callback webhook.

Run: pytest tests/factory/test_pipeline/test_deployer_integrations.py -v
```

---

### WP-A5 — Deployer: Remote Provisioning (Railway + Docker Compose Export)

**Why:** Today the Provisioner only runs containers on the factory's own machine via local Docker. Real deployments go to the client's cloud or to a hosted URL. Need two additional provisioning modes: Railway (for Cognisia-hosted web deployments) and server-export (for client-run Docker Compose installations).

**Files to modify:**
- `factory/pipeline/deployer/provisioner.py` (dispatch on deployment_format)
- `factory/pipeline/deployer/providers/railway.py` (new)
- `factory/pipeline/deployer/providers/docker_compose_export.py` (new)
- `factory/pipeline/deployer/providers/local_docker.py` (extract existing logic)
- `factory/config.py` (Railway API token)

**Acceptance criteria:**
- Provisioner reads `deployment_format` and dispatches:
  - `web` → Railway provider: pushes image to Railway's container registry via their API, creates a service, configures domain, sets env vars, returns `access_url = https://<employee-name>.up.railway.app`.
  - `server` → DockerCompose export provider: generates `<build_dir>/deploy/docker-compose.yml` + README, uploads as `server_package` artifact, sets `access_url=None` (client runs it), status="PENDING_CLIENT_INSTALL".
  - `local` (existing) → preserved for evaluator/dev use only.
- Railway provider uses the official Railway GraphQL API; rate-limit errors trigger exponential backoff up to 3 retries.
- New test `tests/factory/test_pipeline/test_deployer_providers.py` with mocked Railway API covers all three modes.

**Codex prompt:**
```
Split Forge's Provisioner into pluggable providers: local_docker, railway,
docker_compose_export.

Context:
- factory/pipeline/deployer/provisioner.py (current — local Docker only)
- factory/models/deployment.py (DeploymentFormat enum)
- factory/models/build.py (BuildArtifact)

Steps:
1. Create directory factory/pipeline/deployer/providers/ with __init__.py.
2. Move the existing logic in provisioner.py into
   providers/local_docker.py as async provision_local(deployment, build).
3. Create providers/railway.py. Uses httpx to call Railway's GraphQL API
   at https://backboard.railway.app/graphql/v2 with bearer token from
   factory.config.RAILWAY_API_TOKEN:
     - Push the image tarball via railway upload mutation
     - Create service with env vars from the build's manifest
     - Configure domain <employee_name>-<short_id>.up.railway.app
     - Poll for deploy complete (max 10 min)
     - Set deployment.access_url to the resolved HTTPS URL
   Implement exponential backoff for 429s (3 retries, base 2s).
4. Create providers/docker_compose_export.py. Generate:
     <build_dir>/deploy/docker-compose.yml
     <build_dir>/deploy/.env.example
     <build_dir>/deploy/README.md (installation instructions)
   Zip the deploy/ folder, upload via artifact_store.store_file as
   artifact_type="server_package". Set deployment.access_url=None,
   deployment.status="PENDING_CLIENT_INSTALL".
5. Rewrite provisioner.py as a dispatcher:
     if deployment.format == "web": provision_railway(deployment, build)
     elif deployment.format == "server": provision_server(deployment, build)
     elif deployment.format == "local": provision_local(deployment, build)
6. Add RAILWAY_API_TOKEN to factory/config.py Pydantic settings.
7. Write tests/factory/test_pipeline/test_deployer_providers.py with
   respx-mocked Railway API covering web success, web retry-after-429,
   server-export creating correct files, local still working for evaluator.

Run: pytest tests/factory/test_pipeline/test_deployer_providers.py -v
```

---

## Phase B — Upgrade Factory Intelligence (LLM-Driven)

Goal: replace the rule-based Analyst and Architect with LLM-driven reasoning. The factory becomes actually autonomous instead of a hardcoded dispatcher.

---

### WP-B1 — Analyst: LLM-Driven Conversation Engine

**Why:** The current Analyst uses keyword matching. A real client conversation has ambiguity, compound requirements, and domain-specific nuance that keywords can't handle.

**Files to modify:**
- `factory/pipeline/analyst/conversation.py` (major rewrite)
- `factory/pipeline/analyst/requirements_builder.py` (major rewrite)
- `factory/pipeline/analyst/prompts/` (new directory)
- `factory/pipeline/analyst/domain_knowledge/` (populate with legal + exec assistant knowledge)
- `factory/api/analyst.py` (conversation endpoints)

**Acceptance criteria:**
- Analyst is a LangGraph graph with nodes: `intent_classifier` → `domain_router` → `question_generator` → `requirements_extractor` → `completeness_checker`.
- Each node is an LLM call with structured output via Instructor against a Pydantic schema.
- `POST /api/v1/analyst/sessions` starts a session and returns the first question.
- `POST /api/v1/analyst/sessions/{id}/messages` accepts the client's reply and returns either the next question or a completed `EmployeeRequirements` document.
- The Analyst knows when it has enough information (no infinite loops) via the `completeness_checker` returning a confidence score ≥ 0.85.
- When complete, the session writes the `EmployeeRequirements` to Postgres and emits a `commission_created` event.
- New test `tests/factory/test_pipeline/test_analyst_conversation.py` with a mocked LLM covers: simple legal-intake commission (3 turns), ambiguous request requiring clarification (5+ turns), incomplete request rejected.

**Codex prompt:**
```
Replace the keyword-based Analyst with a real LLM-driven LangGraph
conversation engine.

Context to read:
- factory/pipeline/analyst/conversation.py (current — keyword-based)
- factory/pipeline/analyst/requirements_builder.py (current)
- factory/models/requirements.py (EmployeeRequirements shape)
- factory/api/analyst.py

Steps:
1. Create factory/pipeline/analyst/prompts/ containing:
     system_prompt.md - Analyst persona, objectives, output contract
     intent_classifier.md - given a message, classify intent
     question_generator.md - given partial requirements, propose next question
     completeness_checker.md - given requirements, score completeness 0-1
2. Populate factory/pipeline/analyst/domain_knowledge/legal.py and
   executive_assistant.py with lists of required fields, typical workflows,
   compliance concerns, example requirements. These get injected as context
   in the question_generator prompt.
3. Rewrite conversation.py as a LangGraph StateGraph with state:
     session_id, org_id, messages, partial_requirements, completeness_score,
     next_question, is_complete
   Nodes:
     intent_classifier(messages) -> intent
     domain_router(intent) -> conditional edge to legal/executive_assistant
     question_generator(partial_requirements, domain) -> next_question
     requirements_extractor(messages, domain) -> partial_requirements
     completeness_checker(partial_requirements) -> score
   Edges: after completeness_checker, if score >= 0.85 route to "complete",
   else route back to question_generator.
4. All LLM calls use component_library.models.anthropic_provider via
   Instructor for structured outputs.
5. Rewrite requirements_builder.py to consume the final state and produce
   a validated EmployeeRequirements.
6. Wire factory/api/analyst.py:
     POST /api/v1/analyst/sessions -> starts graph, returns first question
     POST /api/v1/analyst/sessions/{id}/messages -> resumes graph with
       client reply, returns next question OR final requirements_id
     GET /api/v1/analyst/sessions/{id} -> current state
7. On completion, persist EmployeeRequirements via factory/persistence.py
   and emit "commission_created" event (use structlog with kwargs for now;
   real event bus later).
8. Write tests/factory/test_pipeline/test_analyst_conversation.py with
   a mocked Anthropic client covering:
     - Legal intake, 3 turns, reaches completeness
     - Ambiguous request, 5+ turns with clarification
     - Incomplete request (client gives partial info and quits) produces
       graceful timeout after 10 turns

Run: pytest tests/factory/test_pipeline/test_analyst_conversation.py -v
```

---

### WP-B2 — Architect: LLM-Driven Component Selector

**Why:** Today the selector uses hardcoded baseline lists. Future employee types require manual edits to `LEGAL_BASELINE_COMPONENTS` / `EXECUTIVE_ASSISTANT_COMPONENTS`. An LLM selector can read requirements and select the right components from the registry without code changes.

**Files to modify:**
- `factory/pipeline/architect/component_selector.py` (major rewrite)
- `factory/pipeline/architect/prompts/component_selection.md` (new)
- `component_library/registry.py` (expose `describe_all_components` for prompt context)

**Acceptance criteria:**
- `registry.describe_all_components()` returns a list of `{component_id, category, version, description, config_schema, status}` for every component with status=`production`.
- Selector builds a prompt: requirements + full registry catalog + "select the minimal set of components that satisfy the requirements. Explain each choice. Produce structured JSON."
- LLM output is parsed via Instructor into `list[SelectedComponent]` with per-component `rationale`.
- The selected set is validated: every required capability must map to at least one component; fail with an ArchitectError if not.
- Rule-based baseline lists remain as a fallback (used when `USE_LLM_ARCHITECT=false`).
- New test `tests/factory/test_pipeline/test_architect_selector_llm.py` with a mocked LLM covers: legal intake selection, executive assistant selection, multi-domain requirement (both legal + exec), unsatisfiable requirement rejected.

**Codex prompt:**
```
Replace the rule-based Architect component selector with an LLM-driven one.

Context:
- factory/pipeline/architect/component_selector.py (current — hardcoded lists)
- factory/models/blueprint.py (SelectedComponent shape)
- factory/models/requirements.py (EmployeeRequirements shape)
- component_library/registry.py
- component_library/status.py

Steps:
1. Extend component_library/registry.py with describe_all_components() ->
   list[ComponentDescription]. ComponentDescription is a new Pydantic model
   with {component_id, category, version, description, config_schema_json,
   status}. Populate description and config_schema_json by reading each
   component's docstring and Pydantic config model.
2. Create factory/pipeline/architect/prompts/component_selection.md:
     - Architect persona
     - Input: EmployeeRequirements JSON + component catalog JSON
     - Task: select minimal component set that satisfies every required
       capability; output list of {component_id, category, config,
       rationale}
     - Output contract: strict JSON matching SelectedComponentWithRationale
3. Extend factory/models/blueprint.py: add SelectedComponent.rationale: str
4. Rewrite component_selector.py:
     select_components(requirements) -> list[SelectedComponent]
     If config.USE_LLM_ARCHITECT:
         call anthropic_provider with component_selection prompt via Instructor
         parse into list[SelectedComponent]
         validate against required capabilities
     Else:
         fall back to existing hardcoded LEGAL_BASELINE / EXECUTIVE_ASSISTANT
5. Add USE_LLM_ARCHITECT=False default in factory/config.py (opt-in for now).
6. Add ArchitectError raised when validation fails.
7. Write tests/factory/test_pipeline/test_architect_selector_llm.py with
   mocked LLM covering:
     - Legal intake → selects text_processor, document_analyzer, email_tool,
       operational_memory, audit_system at minimum
     - Executive assistant → selects scheduler, calendar, messaging tools
     - Compound requirement → selects union
     - Bogus requirement (requirement unsatisfiable by library) → raises

Run: pytest tests/factory/test_pipeline/test_architect_selector_llm.py -v
```

---

### WP-B3 — Architect: Gap Analyzer + Workflow Designer

**Why:** The selector picks components. But the components have to be wired into a LangGraph workflow, and some requirements don't map to any library component (they need the Generator to produce custom code). These two steps are currently rule-based or missing.

**Files to modify:**
- `factory/pipeline/architect/gap_analyzer.py` (LLM-driven)
- `factory/pipeline/architect/workflow_designer.py` (new)
- `factory/pipeline/architect/blueprint_builder.py` (integrate workflow graph)
- `factory/pipeline/architect/prompts/gap_analysis.md` (new)
- `factory/pipeline/architect/prompts/workflow_design.md` (new)
- `factory/models/blueprint.py` (add `workflow_graph: WorkflowGraphSpec`)

**Acceptance criteria:**
- `gap_analyzer.identify_gaps(requirements, selected_components)` uses an LLM to find capabilities the requirements need but no selected component provides; outputs a list of `CustomCodeSpec` objects.
- `workflow_designer.design_workflow(requirements, components, gaps)` uses an LLM to produce a `WorkflowGraphSpec` (nodes list, edges list with conditions, entry point, terminal nodes).
- `WorkflowGraphSpec` validates: every node references either a selected component or a custom code spec; the graph is connected; at least one terminal node.
- `blueprint_builder.assemble_blueprint` puts it all together: selected components + gaps + workflow graph + configs.
- The `Employee Engine` can later instantiate this graph dynamically (deferred to WP-B4).
- New test `tests/factory/test_pipeline/test_architect_workflow.py` asserts a legal intake requirement produces a sensible graph (intake_parser → entity_extractor → conflict_checker → draft_generator → confidence_scorer → terminal), with mocked LLM.

**Codex prompt:**
```
Build the LLM-driven Gap Analyzer and Workflow Designer for the Forge
Architect.

Context:
- factory/pipeline/architect/gap_analyzer.py (current — unknown depth)
- factory/pipeline/architect/blueprint_builder.py
- factory/models/blueprint.py (EmployeeBlueprint, CustomCodeSpec)
- factory/models/requirements.py

Steps:
1. Extend factory/models/blueprint.py:
     class WorkflowNode(BaseModel):
         node_id: str
         component_id: str | None  # reference to selected component
         custom_spec_id: str | None  # reference to a CustomCodeSpec
         config: dict[str, Any] = {}
     class WorkflowEdge(BaseModel):
         from_node: str
         to_node: str
         condition: str | None  # e.g. "confidence > 0.7", "has_conflict"
     class WorkflowGraphSpec(BaseModel):
         nodes: list[WorkflowNode]
         edges: list[WorkflowEdge]
         entry: str
         terminals: list[str]
     EmployeeBlueprint gains: workflow_graph: WorkflowGraphSpec
   Enforce validation that every node references either component_id or
   custom_spec_id (not both, not neither), graph is connected, at least
   one terminal.
2. Create prompts/gap_analysis.md — given requirements and selected
   components, list capabilities needed but not covered; output
   list[CustomCodeSpec].
3. Create prompts/workflow_design.md — given requirements + components
   + gaps, output a WorkflowGraphSpec. Include few-shot examples for
   legal_intake and executive_assistant.
4. Rewrite gap_analyzer.py identify_gaps(requirements, components) ->
   list[CustomCodeSpec]. LLM call via Instructor.
5. Create workflow_designer.py design_workflow(requirements, components,
   gaps) -> WorkflowGraphSpec. LLM call via Instructor with validation.
6. Update blueprint_builder.py assemble_blueprint(requirements, components,
   gaps, workflow_graph) -> EmployeeBlueprint.
7. Update designer.py to call workflow_designer between gap_analyzer
   and assemble_blueprint.
8. Write tests/factory/test_pipeline/test_architect_workflow.py covering:
     - Legal intake produces graph with extract → qualify → conflict_check
       → draft → score → terminal
     - Executive assistant produces different graph centered on scheduler
     - Graph validation rejects disconnected node
     - Graph validation rejects node with no component and no spec

Run: pytest tests/factory/test_pipeline/test_architect_workflow.py -v
```

---

### WP-B4 — Employee Engine: Dynamic Graph Loading from Blueprint

**Why:** Today the Engine has a hardcoded workflow registry (`legal_intake`, `executive_assistant`). When the Architect designs a novel workflow (from B3), the Engine can't run it. The Engine must read `WorkflowGraphSpec` from the employee's config at runtime and dynamically construct the LangGraph.

**Files to modify:**
- `employee_runtime/core/engine.py`
- `employee_runtime/workflows/dynamic_builder.py` (new)
- `employee_runtime/workflows/__init__.py`
- `factory/pipeline/builder/config_generator.py` (write workflow_graph into config.yaml)

**Acceptance criteria:**
- On startup the Engine reads `config.workflow_graph` (a `WorkflowGraphSpec` serialized to dict).
- `dynamic_builder.build_graph(spec, components)` iterates `spec.nodes`, creates a LangGraph node per component (using the component's `execute` method as the node function), adds edges with conditional routing derived from `edge.condition` strings (support: `field >= N`, `field == value`, `field in [...]`, `has_<key>`).
- Entry point and terminal nodes are configured from the spec.
- Existing `legal_intake` and `executive_assistant` workflows are refactored to produce `WorkflowGraphSpec` fixtures, not hand-written graph code, ensuring the dynamic path is the default.
- New test `tests/runtime/test_dynamic_workflow.py` builds a minimal graph from a spec and runs it end-to-end against mocked components.

**Codex prompt:**
```
Make the Forge Employee Engine build its LangGraph dynamically from a
WorkflowGraphSpec at startup, instead of using a hardcoded workflow
registry.

Context:
- employee_runtime/core/engine.py (current hardcoded registry)
- employee_runtime/workflows/legal_intake.py (existing hand-written graph)
- factory/models/blueprint.py (WorkflowGraphSpec from WP-B3)
- factory/pipeline/builder/config_generator.py

Steps:
1. Create employee_runtime/workflows/dynamic_builder.py:
     build_graph(spec: dict, components: dict[str, BaseComponent]) -> StateGraph
     - Iterate spec["nodes"]. For each node, resolve its component (via
       components[node["component_id"]]) or generated module (via
       importlib on node["custom_spec_id"]).
     - Wrap component.execute (or generated function) as a LangGraph node
       that reads EmployeeState, calls execute, returns state updates.
     - Iterate spec["edges"]. If edge.condition is empty, add as straight
       edge. Else parse condition DSL (support "field >= N", "field == X",
       "field in [a,b,c]", "has_<key>") and add as conditional_edge.
     - Set entry point from spec["entry"], set END for terminal nodes.
     - Compile and return.
2. Create a minimal condition DSL parser condition_to_callable(cond: str,
   state: dict) -> bool. Support the 4 operators above. Reject unknown
   operators with a clear error.
3. Refactor engine.py to:
     - Read self._config["workflow_graph"] (dict from config.yaml)
     - Call dynamic_builder.build_graph(spec, self._components)
     - Remove the hardcoded workflow registry
4. Convert employee_runtime/workflows/legal_intake.py into
   employee_runtime/workflows/fixtures/legal_intake_spec.json — a
   WorkflowGraphSpec JSON — instead of Python code. Same for
   executive_assistant. Use these as seed fixtures for tests and for the
   Architect's few-shot examples.
5. Update config_generator.py to embed blueprint.workflow_graph.model_dump()
   into config.yaml as workflow_graph: {...}.
6. Write tests/runtime/test_dynamic_workflow.py:
     - Build graph from legal_intake_spec.json with mock components
     - Run process_task and assert expected state transitions
     - Test conditional edge: confidence >= 0.7 routes to terminal,
       confidence < 0.7 routes to human_review
     - Test unknown condition operator raises

Run: pytest tests/runtime/test_dynamic_workflow.py -v
```

---

## Phase C — Implement the Safety Architecture (The Moat)

Goal: replace the shallow "production"-marked quality modules with real implementations of the proprietary safety architecture.

---

### WP-C1 — Deliberation Council (Real Implementation)

**Why:** This is the single highest-value unimplemented module in the codebase. The current `employee_runtime/modules/deliberation.py` is a 10-line stub. The current `component_library/quality/adversarial_review.py` is a keyword match. The real system is adversarial multi-model debate with structured completion criteria.

**Files to modify:**
- `employee_runtime/modules/deliberation.py` (major implementation)
- `component_library/quality/adversarial_review.py` (replace with real Council wrapper)
- `employee_runtime/modules/deliberation/` (new subdirectory for advocates, challengers, adjudicator, supervisor)
- `employee_runtime/modules/deliberation/prompts/` (new)
- `factory/pipeline/builder/config_generator.py` (emit council config)

**Acceptance criteria:**
- `DeliberationCouncil.deliberate(proposal: Proposal, context: dict) -> Verdict` runs:
  1. `N_advocates` (configurable, default 2) parallel LLM calls, each a different model (e.g. Claude Sonnet + Claude Opus + GPT-4o), each instructed to build the strongest case FOR the proposal.
  2. `N_challengers` parallel LLM calls, different models, each instructed to build the strongest case AGAINST.
  3. `adjudicator` LLM call (typically a stronger/different model) reads all advocate and challenger arguments, produces `Verdict { approved: bool, confidence: float, majority_concerns: list[str], dissenting_views: list[str], reasoning: str }`.
  4. `process_supervisor` LLM call reads the debate and flags if advocates and challengers converged too early (echo chamber), argued past each other, or produced contradictions within a single side. If flagged, re-run with different models.
- Structured completion criteria prevent infinite loops: max 3 re-runs, max wall-clock time configurable (default 10 minutes).
- Client can tune: `N_advocates`, `N_challengers`, `models_per_role`, `enable_re_runs`, `max_time_seconds`, `trigger_conditions` (which actions require the Council).
- Result persisted via `audit_system` with full argument texts for later explainability.
- New test `tests/runtime/test_deliberation_council.py` with a mocked litellm covers: simple approval (both sides agree), contested approval (challengers dissent but adjudicator approves), rejection, supervisor-forced re-run, time-limit exceeded.

**Codex prompt:**
```
Implement the real Forge Deliberation Council. This replaces the 10-line
stub in employee_runtime/modules/deliberation.py and the keyword-match
placeholder in component_library/quality/adversarial_review.py.

READ FIRST: the existing stubs, and CLAUDE.md section on "safety
architecture". Never simplify the adversarial structure — that warning
in the stub is real.

Architecture:
- Advocates (2-3) argue FOR a proposal. Different models.
- Challengers (2-3) argue AGAINST. Different models.
- Adjudicator weighs the debate. Usually the strongest model.
- Process Supervisor detects echo chambers and forces re-runs.

Steps:
1. Create employee_runtime/modules/deliberation/ directory:
     __init__.py
     council.py           # DeliberationCouncil main class
     advocate.py          # single advocate LLM call
     challenger.py        # single challenger LLM call
     adjudicator.py       # weighs debate, produces Verdict
     supervisor.py        # detects echo-chamber, forces rerun
     prompts/
       advocate.md
       challenger.md
       adjudicator.md
       supervisor.md
     schemas.py           # Proposal, Argument, Verdict, SupervisorReport
2. Implement schemas.py as Pydantic models:
     Proposal {proposal_id, content, context, risk_tier}
     Argument {role: "advocate"|"challenger", model: str, reasoning: str, key_points: list[str]}
     Verdict {approved, confidence, majority_concerns, dissenting_views, reasoning}
     SupervisorReport {rerun_needed, reason, issues: list[str]}
3. Implement advocate.py and challenger.py each with async
   argue(proposal, model) -> Argument. Uses litellm_router to dispatch to
   the requested model. Instructor for structured output.
4. Implement adjudicator.py async adjudicate(proposal, advocates,
   challengers, model) -> Verdict. Structured output via Instructor.
5. Implement supervisor.py async supervise(advocates, challengers,
   verdict) -> SupervisorReport. Detects: all advocates agree verbatim
   (echo), no challenger raises an advocate-raised point (past each
   other), contradictions within a single role (incoherent).
6. Implement council.py:
     class DeliberationCouncil:
         def __init__(self, config: CouncilConfig): ...
         async def deliberate(self, proposal, context) -> Verdict:
             for attempt in range(self.max_reruns + 1):
                 # Gather arguments in parallel
                 advocate_args = await asyncio.gather(*[
                     advocate.argue(proposal, model)
                     for model in self.advocate_models
                 ])
                 challenger_args = await asyncio.gather(*[
                     challenger.argue(proposal, model)
                     for model in self.challenger_models
                 ])
                 verdict = await adjudicator.adjudicate(
                     proposal, advocate_args, challenger_args,
                     self.adjudicator_model
                 )
                 supervision = await supervisor.supervise(
                     advocate_args, challenger_args, verdict
                 )
                 if not supervision.rerun_needed:
                     break
                 # Swap to different models for rerun
             # Persist full debate to audit_system
             await audit.log_deliberation(proposal, advocates, challengers,
                                          verdict, supervision, attempt)
             return verdict
7. Replace component_library/quality/adversarial_review.py with a
   wrapper that delegates to DeliberationCouncil (keeps the component
   interface so the Architect can still select it).
8. Update factory/pipeline/builder/config_generator.py to emit a
   "deliberation_council" section into config.yaml when the component
   is selected, including advocate_models, challenger_models,
   adjudicator_model, max_reruns, max_time_seconds, trigger_conditions.
9. Integration: the legal_intake workflow should call the Council on
   any draft output above a risk threshold (configurable). Wire this
   as an optional step in the workflow spec.
10. Write tests/runtime/test_deliberation_council.py covering (all with
    mocked litellm):
      - Simple approval (both sides roughly agree → approved)
      - Contested approval (challengers dissent but adjudicator approves
        with low confidence)
      - Rejection (majority of challenger concerns accepted)
      - Supervisor forces rerun (first pass is echo chamber, second
        pass introduces different models and lands on clear verdict)
      - Time limit exceeded (rerun loop aborts, Verdict.approved=False
        with reasoning "exceeded deliberation budget")

Run: pytest tests/runtime/test_deliberation_council.py -v
```

---

### WP-C2 — Autonomy Manager: Real Confidence-Gated Logic

**Why:** Current implementation is a single `score < threshold` check. The real logic is a multi-dimensional decision: `confidence × action_irreversibility × risk_tier × tenant_policy → (autonomous | approval_required | escalate_to_supervisor)`.

**Files to modify:**
- `component_library/quality/autonomy_manager.py` (major rewrite)
- `component_library/quality/schemas.py` (new)
- `employee_runtime/core/engine.py` (route decisions through Autonomy Manager before any side-effect tool)

**Acceptance criteria:**
- `AutonomyManager.evaluate(action: ProposedAction, context: dict) -> AutonomyDecision` takes:
  - `action.type` (reversible / semi-reversible / irreversible — e.g. sending external email is irreversible)
  - `action.confidence` (from `confidence_scorer`)
  - `action.estimated_impact` (from context, e.g. dollar value, recipient count)
  - `context.risk_tier` (LOW / MEDIUM / HIGH / CRITICAL)
  - `context.tenant_policy` (per-client tuning)
- Output `AutonomyDecision { mode: "autonomous" | "approval_required" | "escalate", required_approver: str | None, rationale: str }`.
- Decision matrix is configurable via YAML — default matrix covers the 4x3x3 combinations of (irreversibility × confidence-band × risk-tier).
- Every decision logged to `audit_system` with the full context.
- New test `tests/components/quality/test_autonomy_manager.py` covers: low-risk reversible → autonomous, high-risk irreversible → approval required even at high confidence, CRITICAL tier with any confidence → escalate to human supervisor, tenant policy override.

**Codex prompt:**
```
Replace the single-threshold autonomy_manager with real multi-dimensional
confidence-gated autonomy logic.

Context:
- component_library/quality/autonomy_manager.py (current — single threshold)
- component_library/interfaces.py (QualityModule contract)

Steps:
1. Create component_library/quality/schemas.py with:
     class ProposedAction(BaseModel):
         type: Literal["reversible", "semi_reversible", "irreversible"]
         description: str
         confidence: float  # 0.0 - 1.0
         estimated_impact: dict[str, Any] = {}  # e.g. {"recipients": 500}
     class AutonomyContext(BaseModel):
         risk_tier: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
         tenant_policy: dict[str, Any] = {}
     class AutonomyDecision(BaseModel):
         mode: Literal["autonomous", "approval_required", "escalate"]
         required_approver: str | None = None
         rationale: str
         matched_rule: str
2. Create component_library/quality/autonomy_matrix.yaml — default decision
   matrix:
     - rule_id: "critical_always_escalate"
       match: {risk_tier: "CRITICAL"}
       decision: {mode: "escalate", approver: "supervisor"}
     - rule_id: "irreversible_high_risk"
       match: {action_type: "irreversible", risk_tier: "HIGH"}
       decision: {mode: "approval_required", approver: "supervisor"}
     - rule_id: "irreversible_medium_low_conf"
       match: {action_type: "irreversible", confidence_max: 0.85}
       decision: {mode: "approval_required"}
     ... (cover the full 4x3x4 matrix)
3. Rewrite autonomy_manager.py:
     class AutonomyManager(QualityModule):
         async def initialize(self, config):
             self._matrix = load_matrix(config.get("matrix_path",
                 "autonomy_matrix.yaml"))
             self._tenant_overrides = config.get("tenant_overrides", {})
         async def evaluate(self, input_data) -> AutonomyDecision:
             action = ProposedAction(**input_data["action"])
             ctx = AutonomyContext(**input_data["context"])
             # Apply tenant overrides first (highest priority)
             # Then match against the matrix in order
             # Return the first matched decision
             # Log to audit_system
4. In employee_runtime/core/engine.py, add a pre-action hook: before any
   node calls a ToolIntegration.invoke, call autonomy_manager.evaluate.
   If mode != "autonomous", set state.requires_human_approval=True,
   state.escalation_reason=decision.rationale, and route to approval_gate
   via conditional edge.
5. Write tests/components/quality/test_autonomy_manager.py covering:
     - Reversible + high confidence + LOW risk → autonomous
     - Irreversible + high confidence + HIGH risk → approval_required
     - Any + CRITICAL risk → escalate
     - Reversible + low confidence + MEDIUM risk → approval_required
     - Tenant override: tenant_policy.force_approval_all=True → approval
       regardless of other inputs

Run: pytest tests/components/quality/test_autonomy_manager.py -v
```

---

### WP-C3 — Explainability Engine: Real Reasoning Records

**Why:** Today `explainability.py` is a thin stub. The product needs real reasoning records the client can click into from the Activity panel: what the employee decided, why, what alternatives it considered, what evidence it used.

**Files to modify:**
- `component_library/quality/explainability.py` (major rewrite)
- `component_library/quality/schemas.py` (add ReasoningRecord)
- `employee_runtime/core/engine.py` (emit a ReasoningRecord at every major decision node)
- `employee_runtime/core/api.py` (expose `GET /api/v1/reasoning/{task_id}`)
- `portal/employee_app/components/ReasoningModal.tsx` (new — renders records)

**Acceptance criteria:**
- `ExplainabilityEngine.capture(decision: DecisionPoint) -> ReasoningRecord` captures: inputs considered, alternatives considered (with scores), the chosen path, confidence, evidence sources cited, modules invoked, total cost (tokens + ms).
- Records are persisted in a dedicated `reasoning_records` Postgres table with one row per task_id × node_id.
- The Activity panel in the Employee App renders each record as a click-through item opening a modal with full details.
- Every node in the dynamic graph can opt-in by wrapping its output with `ExplainabilityEngine.capture(...)`.
- New test `tests/components/quality/test_explainability.py` covers capture, retrieval, and API endpoint.

**Codex prompt:**
```
Replace the explainability stub with a real reasoning-record engine.

Context:
- component_library/quality/explainability.py (current stub)
- employee_runtime/core/engine.py
- employee_runtime/core/api.py
- portal/employee_app/app/page.tsx and components/

Steps:
1. Extend component_library/quality/schemas.py:
     class Alternative(BaseModel):
         option: str
         score: float
         why_not_chosen: str
     class EvidenceSource(BaseModel):
         source_type: str  # "knowledge_base", "web_search", "email", "document"
         reference: str
         content_snippet: str
     class ReasoningRecord(BaseModel):
         record_id: UUID
         task_id: UUID
         node_id: str
         decision: str
         rationale: str
         inputs_considered: dict[str, Any]
         alternatives: list[Alternative]
         evidence: list[EvidenceSource]
         confidence: float
         modules_invoked: list[str]
         token_cost: int
         latency_ms: int
         created_at: datetime
2. Add Alembic migration for a reasoning_records table (separate from the
   main audit_events — this is for UI consumption, not audit).
3. Rewrite explainability.py:
     class ExplainabilityEngine(QualityModule):
         async def initialize(self, config): ...
         async def capture(self, decision: DecisionPoint) -> ReasoningRecord:
             # Build a ReasoningRecord from the decision point
             # Persist to reasoning_records table
             # Return the record
         async def get_records(self, task_id) -> list[ReasoningRecord]:
             # Fetch all records for a task, ordered by created_at
4. In employee_runtime/core/engine.py, add a wrapper helper
   with_explainability(node_fn) that wraps a LangGraph node and emits a
   ReasoningRecord after every call (if the engine's config has
   explainability enabled).
5. In employee_runtime/core/api.py, add:
     GET /api/v1/reasoning/{task_id} -> list[ReasoningRecord]
     GET /api/v1/reasoning/record/{record_id} -> ReasoningRecord
6. Create portal/employee_app/components/ReasoningModal.tsx:
     - Takes a record_id
     - Fetches the record via /api/v1/reasoning/record/{id}
     - Renders: decision, rationale, alternatives with why-not-chosen,
       evidence sources with click-through, modules invoked, cost
7. Wire the Activity panel in SidebarPanels.tsx: each activity item that
   has a record_id becomes clickable and opens the modal.
8. Write tests/components/quality/test_explainability.py covering
   capture, retrieval, and the API endpoints (with a test Postgres via
   pytest-asyncio fixtures).

Run: pytest tests/components/quality/test_explainability.py -v
```

---

### WP-C4 — Compliance Rules: OPA Integration

**Why:** The `compliance_rules` component is currently a stub. Regulated industries (legal, healthcare, finance) need real policy enforcement — not hand-coded Python rules but a declarative policy engine the Architect can configure per industry.

**Files to modify:**
- `component_library/quality/compliance_rules.py` (rewrite around OPA)
- `component_library/quality/policies/` (new directory)
- `component_library/quality/policies/legal.rego` (new)
- `component_library/quality/policies/healthcare.rego` (new, skeletal)
- `docker-compose.yml` (add OPA service for local dev)

**Acceptance criteria:**
- OPA runs as a sidecar or embedded via the `opa-python-client` library.
- `ComplianceRules.evaluate(action_or_output, policy_name)` sends the input to OPA and receives a `PolicyDecision { allowed: bool, violations: list[str], required_remediation: list[str] }`.
- Each industry has a Rego policy file: legal (no unauthorized legal advice, conflict rules, privilege), healthcare (HIPAA PHI handling), finance (reg-disclosure).
- New policy files can be dropped in by the Architect at build time.
- Test `tests/components/quality/test_compliance_rules.py` uses a real OPA test harness (via `opa eval` subprocess) and covers: legal_advice rejection, conflict detection, healthcare PHI scrubbing requirement.

**Codex prompt:**
```
Replace the compliance_rules stub with real OPA-based policy enforcement.

Context:
- component_library/quality/compliance_rules.py (current stub)
- docker-compose.yml

Install: opa-python-client (or subprocess opa CLI if simpler for tests)

Steps:
1. Add opa service to docker-compose.yml:
     opa:
       image: openpolicyagent/opa:latest-envoy
       command: run --server --addr=0.0.0.0:8181
       ports: ["8181:8181"]
       volumes: [./component_library/quality/policies:/policies]
2. Create component_library/quality/policies/legal.rego:
     package forge.legal
     default allow = false
     deny_legal_advice contains msg if {
         input.action_type == "email_send"
         regex.match(`(?i)you should (sue|file)|I recommend (filing|suing)`,
                     input.content)
         msg := "Contains direct legal advice — licensed attorney required"
     }
     deny_conflict contains msg if {
         input.entities[_] in data.conflicts.known
         msg := "Conflict of interest detected"
     }
     violations := [v | v := deny_legal_advice[_]] ++ [v | v := deny_conflict[_]]
     allow := count(violations) == 0
3. Create component_library/quality/policies/healthcare.rego (skeletal —
   one example rule about PHI in outputs).
4. Rewrite compliance_rules.py:
     class ComplianceRules(QualityModule):
         async def initialize(self, config):
             self._opa_url = config.get("opa_url", "http://opa:8181")
             self._policy_name = config.get("policy_name", "legal")
             self._conflicts_data = config.get("conflicts", [])
         async def evaluate(self, input_data) -> PolicyDecision:
             # PUT conflicts data to /v1/data/conflicts/known
             # POST input to /v1/data/forge/{policy_name}/allow (and violations)
             # Return PolicyDecision(allowed, violations, required_remediation)
5. Add PolicyDecision to component_library/quality/schemas.py.
6. Write tests/components/quality/test_compliance_rules.py with a
   test-mode that uses `opa eval` subprocess against the .rego files,
   covering:
     - Clean email → allowed
     - Email with "you should sue" → denied with legal_advice violation
     - Email mentioning a known conflict entity → denied with conflict
     - Healthcare policy rejects PHI leakage

Run: pytest tests/components/quality/test_compliance_rules.py -v
```

---

## Phase D — Fill in the Component Library

Goal: implement the components currently marked `stub` or `reference` so the Architect has a full palette.

---

### WP-D1 — Real Work Capabilities: research_engine, data_analyzer, monitor_scanner

**Why:** The Architect can't assemble non-legal-intake employees without these. `monitor_scanner` is also the Pulse Engine's core signal-scanning primitive.

**Files to modify:**
- `component_library/work/research_engine.py` (24 → ~200 lines)
- `component_library/work/data_analyzer.py` (24 → ~200 lines)
- `component_library/work/monitor_scanner.py` (24 → ~250 lines)
- `component_library/work/schemas.py` (add their schemas)
- `tests/components/work/test_research_engine.py`, `test_data_analyzer.py`, `test_monitor_scanner.py` (new)
- `component_library/status.py` (flip each from stub/reference to production)

**Acceptance criteria per component:**
- **research_engine**: given a question + source list (web, knowledge_base, docs), runs parallel searches, synthesizes findings with citations, returns `ResearchReport { question, sources_used, key_findings: list[Finding], contradictions: list[str], confidence }`.
- **data_analyzer**: given tabular data (CSV / JSON / SQL query), runs LLM-backed analysis — summary stats, anomaly detection, question answering — returns `DataReport { schema, key_metrics, anomalies, narrative_summary }`.
- **monitor_scanner**: given signal source config, polls the source, extracts relevant events, returns `list[Signal]`. Used by Pulse Engine.
- All three: real implementations calling `anthropic_provider`, `search_tool`, `knowledge_base` as needed. Not stubs.
- All three flip to `status=production` in `status.py`.

**Codex prompt:**
```
Implement the three stub work capabilities: research_engine,
data_analyzer, monitor_scanner.

Context for each:
- Read the current stub file
- Read component_library/work/text_processor.py as a working example
- Read component_library/work/schemas.py
- Read component_library/interfaces.py

For research_engine.py (~200 lines):
  class ResearchEngine(WorkCapability):
      async def execute(self, input_data: ResearchRequest) -> ResearchReport:
          - Read input_data.question, input_data.sources (list of source refs)
          - Run parallel search calls: web (via search_tool), knowledge_base,
            document_ingestion
          - For each result, extract relevant snippets via an LLM call
          - Synthesize findings via a second LLM call, noting contradictions
          - Emit structured ResearchReport with citations back to sources
  Schemas in schemas.py: ResearchRequest, Finding, ResearchReport.

For data_analyzer.py (~200 lines):
  class DataAnalyzer(WorkCapability):
      async def execute(self, input_data: DataAnalysisRequest) -> DataReport:
          - Accept tabular data as CSV string, list[dict], or SQL query
          - Compute basic stats locally (pandas) for numeric columns
          - Use LLM for narrative summary and anomaly detection
          - Return DataReport with schema inference, key_metrics, anomalies,
            and a narrative_summary
  Schemas: DataAnalysisRequest, DataReport.

For monitor_scanner.py (~250 lines):
  class MonitorScanner(WorkCapability):
      async def execute(self, input_data: ScanRequest) -> list[Signal]:
          - Read input_data.source (email / web_feed / calendar / doc_store)
          - Dispatch to the appropriate tool component
          - For each item, run an LLM classifier to decide if it's a
            candidate signal
          - Return list[Signal] with source, content, timestamp, raw_score
          - The Pulse Engine later applies significance scoring to raw_score
  Schemas: ScanRequest, Signal.

For each:
- Flip status in component_library/status.py to "production"
- Write tests/components/work/test_<name>.py with mocked LLM + tool calls
- Every test covers: happy path, empty input, error handling,
  schema validation

Run: pytest tests/components/work/ -v
```

---

### WP-D2 — Real Tool Integrations: search_tool, file_storage_tool, document_ingestion, custom_api_tool

**Why:** The stub tools prevent several work components from being fully functional.

**Files to modify:**
- `component_library/tools/search_tool.py` (Tavily integration)
- `component_library/tools/file_storage_tool.py` (S3 / MinIO via boto3)
- `component_library/tools/document_ingestion.py` (Unstructured)
- `component_library/tools/custom_api_tool.py` (generic httpx wrapper with auth)
- `component_library/status.py`
- `tests/components/tools/` (new test files)

**Acceptance criteria:**
- Each tool implements `ToolIntegration.invoke(action, params) -> dict`.
- `search_tool`: actions=[`search`], uses Tavily API, rate-limited, returns normalized results.
- `file_storage_tool`: actions=[`upload`, `download`, `list`, `delete`], uses boto3 against S3 or MinIO (based on config).
- `document_ingestion`: actions=[`parse`, `chunk`, `extract_text`], wraps `unstructured.partition.auto.partition`.
- `custom_api_tool`: actions=[`get`, `post`, `put`, `delete`], generic httpx client with bearer/basic/api-key auth support.
- All flip to `status=production`.

**Codex prompt:**
```
Implement the four stub tool integrations.

Install: tavily-python, boto3, unstructured[all-docs], httpx

For component_library/tools/search_tool.py (Tavily):
  class SearchTool(ToolIntegration):
      async def initialize(self, config):
          self._api_key = config["tavily_api_key"]  # or via env TAVILY_API_KEY
          self._client = TavilyClient(api_key=self._api_key)
      async def invoke(self, action, params):
          if action == "search":
              results = self._client.search(query=params["query"],
                  max_results=params.get("max_results", 5))
              return {"results": [
                  {"url": r["url"], "title": r["title"], "snippet": r["content"]}
                  for r in results["results"]
              ]}
          raise ValueError(f"Unknown action: {action}")

For component_library/tools/file_storage_tool.py (S3/MinIO):
  Use boto3 with endpoint_url from config (MinIO local) or AWS.
  Actions: upload, download, list, delete. Include tenant_id as prefix
  in every key (multi-tenant isolation).

For component_library/tools/document_ingestion.py (Unstructured):
  Actions:
    parse(file_path or bytes) -> list[Element]
    chunk(elements, max_chunk_size) -> list[Chunk]
    extract_text(file_path) -> str
  Use unstructured.partition.auto.partition for parse.

For component_library/tools/custom_api_tool.py (generic HTTP):
  Actions: get, post, put, delete
  Config: base_url, auth_type (bearer|basic|apikey|none), auth_config
  Use httpx.AsyncClient with retries for 5xx, respect rate limits on
  429 with Retry-After.

For each:
- Flip status in component_library/status.py to "production"
- Add tests/components/tools/test_<name>.py with respx/moto/mocked
  Unstructured covering happy path, auth failure, rate limit, large
  payload.

Run: pytest tests/components/tools/ -v
```

---

### WP-D3 — Knowledge Base (pgvector)

**Why:** The `knowledge_base` data source is "reference". Without it, employees can't be grounded in client-specific documents (contracts, playbooks, policies).

**Files to modify:**
- `component_library/data/knowledge_base.py` (major implementation)
- `alembic/versions/` (new migration for `knowledge_chunks` table)
- `component_library/status.py`
- `tests/components/data/test_knowledge_base.py`

**Acceptance criteria:**
- `KnowledgeBase.query(query, k=5, filters=None) -> list[Chunk]` uses pgvector's cosine similarity against OpenAI/Voyage embeddings.
- `KnowledgeBase.ingest(document, metadata)` runs document through `document_ingestion` (if not already chunked), generates embeddings, inserts with tenant_id scoping.
- Every row has `tenant_id`, `document_id`, `chunk_index`, `content`, `embedding` (vector(1536)), `metadata` (jsonb).
- Filters support metadata equality matching (e.g. `{"practice_area": "corporate"}`).
- Flip to `status=production`.

**Codex prompt:**
```
Implement the pgvector-backed KnowledgeBase component.

Context:
- component_library/data/knowledge_base.py (current — reference stub)
- component_library/interfaces.py (DataSource contract)
- docker-compose.yml (Postgres has pgvector extension)
- Existing alembic migrations for reference

Steps:
1. Create alembic migration adding knowledge_chunks table:
     id UUID PK
     tenant_id UUID NOT NULL
     document_id UUID NOT NULL
     chunk_index INT NOT NULL
     content TEXT NOT NULL
     embedding vector(1536) NOT NULL
     metadata JSONB DEFAULT '{}'::jsonb
     created_at TIMESTAMPTZ DEFAULT now()
   Indexes:
     CREATE INDEX ON knowledge_chunks USING ivfflat (embedding vector_cosine_ops);
     CREATE INDEX ON knowledge_chunks (tenant_id, document_id);
2. Implement KnowledgeBase:
     class KnowledgeBase(DataSource):
         async def initialize(self, config):
             self._tenant_id = config["tenant_id"]
             self._embedding_model = config.get("embedding_model",
                 "text-embedding-3-small")
             self._client = get_async_engine()
         async def ingest(self, document_id, chunks: list[str], metadata):
             embeddings = await self._embed_batch(chunks)
             # Bulk insert
         async def query(self, query: str, k=5, filters=None) -> list[Chunk]:
             q_embedding = await self._embed(query)
             # SELECT ... ORDER BY embedding <=> :q LIMIT k
             # Apply tenant_id and filter predicates
3. Helper _embed uses OpenAI embeddings via litellm_router.
4. Flip status to "production" in status.py.
5. Write tests/components/data/test_knowledge_base.py with a test
   Postgres (via pytest-asyncio + docker-compose) covering:
     - Ingest + retrieve
     - Cross-tenant isolation (tenant A cannot see tenant B's chunks)
     - Metadata filter
     - Empty result

Run: pytest tests/components/data/test_knowledge_base.py -v
```

---

## Phase E — (skipped — see Track 2)

## Phase G — Cross-Cutting Observability & Safety

Goal: wire the OSS safety/observability stack that Phase 1 deferred.

---

### WP-G1 — LangFuse Tracing on Every LLM Call

**Why:** You can't debug or optimize what you can't see. Every LLM call, every component invocation, every workflow step should be traced.

**Files to modify:**
- `component_library/models/anthropic_provider.py`
- `component_library/models/litellm_router.py`
- `employee_runtime/core/engine.py` (wrap every node)
- `factory/config.py` (LangFuse config)
- `docker-compose.yml` (LangFuse service or SaaS config)

**Acceptance criteria:**
- Every call through `anthropic_provider.generate` or `litellm_router.complete` creates a LangFuse generation with full input, output, model, token counts, cost.
- Every employee workflow run creates a LangFuse trace with one span per node.
- Every factory pipeline stage creates a LangFuse trace with one span per stage.
- A `LANGFUSE_ENABLED=false` env flag cleanly disables tracing without breaking anything.

**Codex prompt:**
```
Wire LangFuse tracing across every LLM call and every workflow / pipeline
execution.

Install: langfuse

Steps:
1. Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST,
   LANGFUSE_ENABLED to factory/config.py.
2. Add langfuse service to docker-compose.yml (or document SaaS config).
3. Create factory/observability/langfuse_client.py with a lazy-initialized
   singleton client. If LANGFUSE_ENABLED is False, return a no-op client.
4. Update component_library/models/anthropic_provider.py:
     Wrap every generate() call with langfuse.generation(...) recording
     input, output, model, usage.
5. Update litellm_router.py similarly.
6. Update employee_runtime/core/engine.py:
     Wrap process_task in langfuse.trace(name=workflow_name, user_id=org_id).
     Wrap each node call in langfuse.span.
7. Update factory/workers/pipeline_worker.py:
     Wrap start_pipeline in langfuse.trace(name="factory_pipeline",
         user_id=org_id, session_id=build_id).
     Each stage (Architect, Assembler, Generator, Packager, Evaluator,
     Deployer) wraps in langfuse.span.
8. Write tests/observability/test_langfuse_integration.py asserting
   a disabled LangFuse doesn't error and an enabled LangFuse produces
   traces (using langfuse test mode).

Run: pytest tests/observability/ -v
```

---

### WP-G2 — Guardrails AI for Input Sanitization

**Why:** Current input_protection is hand-coded. Guardrails AI has battle-tested validators for prompt injection, PII, jailbreak attempts.

**Files to modify:**
- `component_library/quality/input_protection.py`
- `tests/components/quality/test_input_protection.py`

**Codex prompt:**
```
Upgrade input_protection to use Guardrails AI.

Install: guardrails-ai

Steps:
1. Replace the hand-coded checks in input_protection.py with Guardrails
   validators: DetectPII, DetectPromptInjection, ToxicLanguage.
2. Config specifies which validators to apply (via YAML).
3. Return structured ProtectionReport{ passed, violations, sanitized_input }.
4. Update tests.

Run: pytest tests/components/quality/test_input_protection.py -v
```

---

### WP-G3 — DeepEval Test Harness for Evaluator

**Why:** The Evaluator's functional/security/behavioral tests are currently hand-rolled. DeepEval gives you a structured eval framework with metrics like hallucination, answer relevancy, faithfulness.

**Files to modify:**
- `factory/pipeline/evaluator/functional_tests.py`
- `factory/pipeline/evaluator/behavioral_tests.py`
- `factory/pipeline/evaluator/hallucination_tests.py` (new)
- `factory/pipeline/evaluator/datasets/` (new — per-workflow test cases)

**Codex prompt:**
```
Wrap the Evaluator's test suites in DeepEval for proper metric-based
evaluation.

Install: deepeval

Steps:
1. Create factory/pipeline/evaluator/datasets/legal_intake.jsonl with
   10 realistic intake emails and their expected structured outputs.
2. Refactor functional_tests.py:
     For each dataset case:
       - POST the input to the employee's /api/v1/tasks
       - Get the output
       - Run DeepEval metrics: AnswerRelevancy, Faithfulness, JSONSchema
       - Report pass/fail per case + aggregate
3. Create hallucination_tests.py using DeepEval's HallucinationMetric:
     - For each factual claim in the output, check against the input
       context
     - Fail if hallucination score > threshold
4. behavioral_tests.py stays but gains DeepEval's ToxicityMetric and
   BiasMetric.
5. Tests run inside the ephemeral evaluator container via
   container_runner.

Run: pytest tests/factory/test_pipeline/test_evaluator_deepeval.py -v
```

---

# TRACK 2 — FRONTEND / PORTAL

## Phase E — Polish the Employee App

Goal: raise the employee app from "functional prototype" to "demoable product".

---

### WP-E1 — Rich Inbox Panel (Approvals & Briefings)

**Why:** Today the Inbox renders a raw executive_summary string. Real approvals need action buttons, context, and a proper card layout.

**Files to modify:**
- `portal/employee_app/components/SidebarPanels.tsx` (split Inbox into its own component)
- `portal/employee_app/components/InboxPanel.tsx` (new)
- `portal/employee_app/components/ApprovalCard.tsx` (new)
- `portal/employee_app/components/BriefingCard.tsx` (new)
- `portal/employee_app/lib/api.ts` (new — API client)

**Acceptance criteria:**
- Inbox renders three sections: Approvals, Briefings, Alerts.
- Each Approval is a card with: title, requester, rationale summary, action buttons (Approve / Decline / Modify / See Details), urgency indicator.
- Approve/Decline buttons POST to `/api/v1/approvals/{id}/resolve`; on success the card fades out.
- "See Details" opens a modal showing the full reasoning record (uses `ReasoningModal` from WP-C3).
- Briefings render as structured cards with sections: What Happened, Why It Matters, Recommended Action, Evidence.
- Empty states are genuinely helpful, not just "no items."

**Codex prompt:**
```
Upgrade the Inbox sidebar panel from a raw JSON dump to a rich,
action-capable UI.

Context:
- portal/employee_app/components/SidebarPanels.tsx (current panel)
- portal/employee_app/components/types.ts
- portal/employee_app/app/page.tsx

Steps:
1. Create portal/employee_app/lib/api.ts with typed functions:
     fetchApprovals() -> Approval[]
     resolveApproval(id, decision: "approve"|"decline"|"modify", note?)
     fetchBriefings() -> Briefing[]
     fetchAlerts() -> Alert[]
   All use fetch against NEXT_PUBLIC_API_BASE_URL.
2. Create InboxPanel.tsx with three tabs: Approvals, Briefings, Alerts.
   Use a segmented control for tabs (shadcn/ui Tabs).
3. Create ApprovalCard.tsx:
     Props: approval: Approval, onResolve: (decision) => void
     Layout: title, requester avatar, summary, urgency chip, action row
     Action row has Approve (green), Decline (red), Modify (neutral),
     See Details (link).
     On Approve/Decline click, call resolveApproval, animate the card
     fading out on success.
     "See Details" opens ReasoningModal from WP-C3.
4. Create BriefingCard.tsx with structured sections: What Happened,
   Why It Matters, Recommended Action, Evidence (collapsible). Each
   section uses a distinct subtle background.
5. Split the Inbox section out of SidebarPanels.tsx and replace it with
   <InboxPanel />.
6. Add proper empty states: "No pending approvals — you're all caught up."
   with a subtle illustration (use a simple SVG inline).

Run: cd portal/employee_app && npm run lint && npm run build
```

---

### WP-E2 — Activity Timeline with Reasoning Click-Through

**Why:** Activity currently shows event_type strings. Real activity needs time-grouping, event type icons, and click-through to reasoning records.

**Files to modify:**
- `portal/employee_app/components/SidebarPanels.tsx`
- `portal/employee_app/components/ActivityPanel.tsx` (new)
- `portal/employee_app/components/ReasoningModal.tsx` (may exist from WP-C3)

**Codex prompt:**
```
Upgrade Activity panel to a real timeline UI.

Steps:
1. Create ActivityPanel.tsx:
     - Fetch /api/v1/activity?limit=50
     - Group events by day (Today, Yesterday, This Week, Earlier)
     - Each event row: icon (based on event_type), short description,
       timestamp (relative), click handler opening ReasoningModal if
       record_id present.
     - Filter chips at the top: All, Decisions, Communications, Errors.
2. Icons come from lucide-react. Define an event_type → icon map.
3. Replace Activity section in SidebarPanels.tsx with <ActivityPanel />.

Run: cd portal/employee_app && npm run build
```

---

### WP-E3 — Settings Page (Real Configuration UI)

**Why:** Settings is currently a JSON key-value dump. Clients need real form controls to tune their employee.

**Files to modify:**
- `portal/employee_app/app/settings/page.tsx` (new)
- `portal/employee_app/components/SettingsForm.tsx` (new)
- `portal/employee_app/components/OrgMapEditor.tsx` (new)
- `employee_runtime/core/api.py` (settings endpoints)

**Acceptance criteria:**
- Full-page `/settings` route, not just a sidebar panel.
- Sections: Communication Preferences, Approval Rules, Authority Limits, Organizational Map, Integrations, Advanced.
- Each setting uses appropriate form controls (sliders for thresholds, toggles for flags, dropdowns for enums, custom OrgMap editor).
- Changes are validated client-side and persisted via `PATCH /api/v1/settings`.
- Optimistic updates with rollback on error.

**Codex prompt:**
```
Build a real Settings page for the employee app.

Steps:
1. Create app/settings/page.tsx — full route.
2. Sections via shadcn/ui Accordion:
     Communication Preferences (channels, frequency, tone)
     Approval Rules (which actions require approval, by dollar value /
       recipient count / action type)
     Authority Limits (max autonomous action value, max recipients)
     Organizational Map (custom tree editor)
     Integrations (list connected Composio tools, disconnect option)
     Advanced (confidence thresholds, Council config if enabled)
3. Use react-hook-form + zod for validation.
4. Persist to PATCH /api/v1/settings. On error, roll back UI state.
5. Add corresponding GET /api/v1/settings and PATCH /api/v1/settings
   endpoints to employee_runtime/core/api.py.
6. Create OrgMapEditor.tsx: a drag-drop tree editor for the employee's
   colleagues and supervisor chain.

Run: cd portal/employee_app && npm run build
```

---

### WP-E4 — Memory Browser + Editor

**Why:** Currently shows truncated JSON. Clients need to browse, search, edit, and delete operational memory.

**Codex prompt:**
```
Build a real Memory browser page.

Steps:
1. Create app/memory/page.tsx with tabs: Operational Memory, Knowledge
   Base, Working Memory (read-only).
2. Operational Memory tab:
     - Table with columns: Category, Key, Value, Source, Last Updated
     - Search box (client-side filter)
     - Inline edit on click (POST to /api/v1/memory/ops/{key})
     - Delete button per row (with confirmation)
3. Knowledge Base tab:
     - Document list with upload button
     - Click into a doc to see its chunks and metadata
     - Re-index button
4. Wire endpoints in employee_runtime/core/api.py:
     GET /api/v1/memory/ops, PATCH /api/v1/memory/ops/{key},
     DELETE /api/v1/memory/ops/{key}, GET /api/v1/memory/kb/documents,
     POST /api/v1/memory/kb/documents (upload).

Run: cd portal/employee_app && npm run build
```

---

### WP-E5 — Metrics Dashboard

**Why:** Shows JSON key-value. Clients need visualizations.

**Codex prompt:**
```
Build a Metrics dashboard with real charts.

Install: recharts

Steps:
1. Create app/metrics/page.tsx.
2. Top row: 4 KPI cards (Tasks Completed Today, Avg Confidence,
   Human Approvals Needed %, Estimated Hours Saved This Week).
3. Tasks-over-time: recharts LineChart, daily for the past 30 days.
4. Task outcomes: recharts PieChart (Autonomous / Approved / Declined / Errored).
5. Top 5 Most Common Actions: recharts BarChart.
6. Endpoint GET /api/v1/metrics/dashboard aggregates from the audit
   table (add it to employee_runtime/core/api.py).

Run: cd portal/employee_app && npm run build
```

---

### WP-E6 — Electron Integration (Polish)

**Why:** Current electron/main.js is minimal. Need native features: dock badge count, system notifications, file drag-drop handler.

**Codex prompt:**
```
Polish the Electron wrapper with native features.

Steps:
1. Update electron/main.js:
     - Set dock/taskbar badge count based on pending approval count
       (IPC message from renderer).
     - Register system notification handler: when renderer sends
       "notify" IPC with {title, body, action_url}, show a native
       notification and attach a click-through to action_url.
     - File drag-drop: if a file is dropped on the window, forward it
       as an upload to /api/v1/documents/upload.
2. Update electron/preload.js to expose these IPC bridges safely:
     window.forge.setBadgeCount(n)
     window.forge.notify(title, body, action_url)
     window.forge.onFileDropped((path) => ...)
3. In the renderer (Next.js pages), integrate:
     - On inbox fetch, call window.forge.setBadgeCount(approvals.length)
     - On new urgent approval, call window.forge.notify(...)
     - Wire a global drop zone that calls the upload endpoint.

Run: cd portal/employee_app && npm run build && npm run electron:pack
```

---

## Phase F — Factory Portal

Goal: build the internal Cognisia-facing portal where operators commission employees, watch builds, manage the roster.

---

### WP-F1 — Commission Flow

**Why:** Today the factory portal is 145 lines of skeleton. No commission UI exists.

**Codex prompt:**
```
Build the Commission flow for the factory portal.

Steps:
1. Create portal/factory_portal/app/commission/page.tsx:
     - Step 1: client info (org, primary contact, industry)
     - Step 2: start an Analyst session (POST /api/v1/analyst/sessions)
     - Step 3: chat UI consuming the Analyst session — streams questions,
       accepts answers, displays partial requirements
     - Step 4: review final requirements, confirm, submit
         → POST /api/v1/commissions
2. Once submitted, redirect to /builds/{build_id} (WP-F2).

Run: cd portal/factory_portal && npm run build
```

---

### WP-F2 — Build Tracker (Live Logs)

**Why:** Operators need to watch pipeline runs in real time.

**Codex prompt:**
```
Build the Build Tracker page.

Steps:
1. Create app/builds/[id]/page.tsx:
     - Header: build_id, status, requirements summary
     - Vertical stage tracker: Architect → Assembler → Generator →
       Packager → Evaluator → Deployer. Each stage has a status
       indicator and expandable logs.
     - Logs stream via WebSocket or SSE from /api/v1/builds/{id}/stream
2. Add SSE endpoint in factory/api/builds.py that streams new BuildLog
   entries as they're created (via Postgres NOTIFY/LISTEN or
   polling-fallback).
3. On failure, show the error detail prominently with a Retry button
   calling /api/v1/builds/{id}/retry.

Run: cd portal/factory_portal && npm run build
```

---

### WP-F3 — Roster & Monitoring

**Codex prompt:**
```
Build the Roster and Monitoring pages.

Steps:
1. Create app/roster/page.tsx:
     - Grid of deployed employee cards, grouped by client
     - Each card: employee name, role, status (green/amber/red based on
       Monitor health), last_task_completed_at, access_url
     - Click opens app/employees/[id]/page.tsx with detail view
2. Create app/employees/[id]/page.tsx:
     - Status, recent activity, last 20 monitoring events, integration
       statuses, version history
     - Actions: Pause, Restart, Rollback to previous version, Update
3. Wire endpoints from factory/api/roster.py and monitoring.py.

Run: cd portal/factory_portal && npm run build
```

---

## 4. Ordering & Time Estimates

Rough sizing — assumes one Codex session per WP, ~1–2 Claude-Sonnet-grade sessions each to land + review + test.

| Phase | WPs | Est. sessions | Critical path? |
| --- | --- | --- | --- |
| A — Factory Output | A1, A2, A3, A4, A5 | 10 | Yes |
| B — Factory Intelligence | B1, B2, B3, B4 | 10 | Yes |
| C — Safety Architecture | C1, C2, C3, C4 | 10 | Partially (C1 yes) |
| D — Component Library | D1, D2, D3 | 6 | After B |
| G — Observability | G1, G2, G3 | 5 | Can interleave |
| E — Employee App | E1–E6 | 8 | Parallel track |
| F — Factory Portal | F1, F2, F3 | 5 | Parallel track |
| **Total** | **28 WPs** | **~54 sessions** | |

At 2 focused Codex sessions per day, this is roughly 4–6 weeks to a demoable V1 with real depth, not scaffolding. Do WP-A1, A3, C1 first — they unblock the most downstream work.

---

## 5. Priority: If You Can Only Do 10 Things

If you had to ship a demoable V1 with a minimal-but-honest feature set, these are the 10 work packages that produce the most demo impact:

1. **WP-A1** — Packager frontend build (so the employee ships with its UI)
2. **WP-A3** — Generator LLM code gen (so the factory can actually generate)
3. **WP-C1** — Deliberation Council (the moat that nothing else in the market has)
4. **WP-B2** — LLM Architect selector (so the factory is autonomous for new employee types)
5. **WP-E1** — Rich Inbox (the highest-visibility part of the app)
6. **WP-E2** — Activity timeline (the second most-visible)
7. **WP-E3** — Settings page (you'll demo configuration)
8. **WP-F1** — Commission flow (how clients start a build)
9. **WP-F2** — Build tracker (what they watch during the build)
10. **WP-G1** — LangFuse tracing (you'll need this to debug the demo)

Everything else can be stubbed, hidden, or deferred for the V1.1 pass.

---

## 6. After Each WP

Every Codex session should end with:

1. `pytest <scoped tests> -v` all passing
2. `ruff check .` and `mypy .` clean on touched files
3. An entry in `DECISIONS.md` if an architectural choice was made
4. A commit message following the existing repo style: `"<Stage>: <specific change>"` (matching the history: "Wire model clients into legal intake components", "Advance runtime autonomy and monitoring for hosted employees")

---

## 7. What NOT to Build in V1

These are Phase 2 and beyond. Codex should refuse if asked:

- Multi-employee app (one employee per app remains V1)
- VM-based computer use (API-only in V1)
- Federated learning across clients (scaffolding exists — don't deepen)
- Autonomous Maintainer (humans trigger updates in V1)
- Phone / SMS channels (Phase 2)
- Custom model fine-tuning (clients use library models in V1)
- Revenue-share billing (flat pricing in V1)

---

End of plan.
