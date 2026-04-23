# Forge — Full Codex Launch-Readiness Plan

Seven self-contained sessions. Each is designed to be pasted into Codex CLI as a single prompt. Run them in order. Days 1-2 and 5-10 require you to initiate and review results personally. Exam-week sessions (A-E) are designed to run autonomously while you check in for 20 minutes.

---

## SESSION 1 — Runway Clearer (Days 1–2)
### Fix: test collection error · infisical pin · gitignore test outputs

**Goal:** Close the three small blockers that prevent a clean test run, so Phase 5 of the test plan can actually execute.

---

Read these files first, in this order. Do not skip any.

1. `tests/runtime/test_task_recovery.py` lines 35–44 — the broken docker availability check
2. `pyproject.toml` — find the `infisical-python` pin in `[project.optional-dependencies]`
3. `.gitignore` — see existing ignore rules
4. `TEST_REPORT.md` and `test_results.xml` — these exist in the repo root and must not be there

---

### Fix 1 of 3 — Test collection crash in `test_task_recovery.py`

**The bug:** `_docker_available()` at line 35 calls `subprocess.run(["docker", "version"], ...)`. When the `docker` binary is not on `PATH`, Python raises `FileNotFoundError` at collection time rather than returning a failed `CompletedProcess`. Because `pytestmark` at line 44 calls `_docker_available()` at module import, the entire test suite fails to collect — not just the docker tests. 169 tests that have nothing to do with docker cannot run.

**The fix:** wrap the `subprocess.run` call in a `try/except FileNotFoundError` that returns `False`.

Find this exact block in `tests/runtime/test_task_recovery.py`:

```python
def _docker_available() -> bool:
    result = subprocess.run(
        ["docker", "version"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0
```

Replace with:

```python
def _docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False
```

**Verify:**

```bash
pytest tests/runtime/test_task_recovery.py --collect-only -q 2>&1 | tail -5
# Must not show "FileNotFoundError". Must show either collected tests or "skipped".

pytest tests/components/ -q --tb=no 2>&1 | tail -3
# Must show 114 passed, 0 errors. If collection fails here, Fix 1 is not complete.
```

---

### Fix 2 of 3 — `infisical-python` version pin

**The bug:** `pyproject.toml` pins `infisical-python>=2.3.6,<3` but PyPI's maximum published version is `2.3.5`. Any environment attempting `pip install -e ".[platform]"` fails with no matching distribution. This silently blocks the `[platform]` extra across all environments.

**The fix:** In `pyproject.toml`, find the line:

```toml
    "infisical-python>=2.3.6,<3",
```

Change it to:

```toml
    "infisical-python>=2.3.5,<3",
```

**Verify:**

```bash
pip install "infisical-python>=2.3.5,<3" --dry-run 2>&1 | tail -3
# Must say "Would install infisical-python-2.3.5" or similar. Must NOT say "No matching distribution".
```

---

### Fix 3 of 3 — Remove committed test output files from git

**The bug:** `TEST_REPORT.md` and `test_results.xml` are tracked in the git index. These are generated outputs from test runs, not source code. They create merge conflicts, contain stale pass/fail data, and will confuse future Codex sessions that read the repo.

**The fix:**

```bash
# Untrack from git index without deleting from disk
git rm --cached TEST_REPORT.md test_results.xml

# Add explicit rules to .gitignore
# Find the "Tests / coverage" section in .gitignore and add these two lines there:
# TEST_REPORT.md
# test_results.xml
```

Add to `.gitignore` under the existing `# Tests / coverage` section:

```
TEST_REPORT.md
test_results.xml
```

**Verify:**

```bash
git ls-files TEST_REPORT.md test_results.xml
# Output must be empty — neither file should appear

git status 2>&1 | grep -E "TEST_REPORT|test_results"
# Should show them as "deleted" (staged) if they existed, or nothing if they didn't
```

---

### Final verification — full suite collects and baseline holds

```bash
# Run the full suite — every group must collect without error
pytest tests/ --collect-only -q 2>&1 | tail -10
# Must show a count of collected tests with zero collection errors

# Run components baseline — must stay green
pytest tests/components/ -q --tb=no 2>&1 | tail -3
# 114 passed, 0 errors

# Run full suite, record pass rate
pytest tests/ --tb=no -q 2>&1 | tail -5
# Target: >=95% pass rate with zero collection errors
```

---

### Commit message

```
fix: test collection crash, infisical pin, gitignore generated outputs

- Wrap subprocess.run(["docker", "version"]) in try/except FileNotFoundError
  so test_task_recovery.py collects cleanly on hosts without Docker in PATH
- Lower infisical-python pin from >=2.3.6 to >=2.3.5 (2.3.6 does not exist on PyPI)
- git rm --cached TEST_REPORT.md test_results.xml; add both to .gitignore
```

### Session summary

Print a short markdown table at the end:

| Fix | Status | Verify output |
|---|---|---|
| test_task_recovery collection | ✅/❌ | paste the tail of `--collect-only` |
| infisical-python pin | ✅/❌ | paste dry-run result |
| gitignore test outputs | ✅/❌ | paste `git ls-files` output |
| Full suite pass rate | X% | paste final pytest summary line |

Do NOT touch any business logic. Do NOT refactor. Do NOT add features.

---
---

## SESSION 2 — Auth Layer (Days 5–8)
### Add bearer token auth to factory API and employee runtime API

**Goal:** Every factory and employee runtime API endpoint except health checks requires a valid bearer token. In production mode, the service refuses to start with a default secret. This is the minimum required before any client-facing deployment.

---

Read these files first:

1. `factory/config.py` — note `factory_jwt_secret` field (already exists), `jwt_algorithm`, `jwt_expiration_minutes`, `is_production` property
2. `factory/main.py` — understand how routers are registered via `api_router`
3. `factory/api/__init__.py` — see all sub-routers included in `api_router`
4. `factory/api/health.py` — the health endpoint that must stay unprotected
5. `employee_runtime/core/api.py` lines 1–80 — understand app structure; note health endpoints at `/health` and `/api/v1/health`
6. `pyproject.toml` — confirm `pyjwt>=2.12.1` is already in core deps (it is; do not add it again)

---

### Part A — Factory API auth

**A1. Startup guard — refuse default secret in production**

In `factory/main.py`, in the `lifespan` async context manager, after `init_engine()` and before `yield`, add this block:

```python
    # Refuse to start in production with a default JWT secret
    _DEFAULT_SECRETS = {"change-me", "forge-factory-dev-secret", "secret", ""}
    if settings.is_production and settings.factory_jwt_secret in _DEFAULT_SECRETS:
        raise RuntimeError(
            "FACTORY_JWT_SECRET must be set to a strong random value in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
```

**A2. Auth dependency — `factory/auth.py` (new file)**

Create `factory/auth.py`:

```python
"""Factory API authentication — bearer token via JWT."""

from __future__ import annotations

from typing import Annotated

import jwt
import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from factory.config import get_settings

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


async def verify_factory_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> dict[str, object]:
    """Validate a bearer JWT. Raise 401 on any failure."""
    settings = get_settings()
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.factory_jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        logger.debug("factory_auth_ok", sub=payload.get("sub"))
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")


FactoryAuth = Annotated[dict[str, object], Depends(verify_factory_token)]
```

**A3. Token issuance endpoint — `factory/api/auth.py` (new file)**

Create `factory/api/auth.py`:

```python
"""Token issuance for the factory API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from factory.config import get_settings

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["auth"])


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


@router.post("/auth/token", response_model=TokenResponse, summary="Exchange API key for JWT")
async def issue_token(body: TokenRequest) -> TokenResponse:
    """Issue a short-lived JWT in exchange for a valid API key.

    For V1, the API key IS the factory_jwt_secret. In V2 this becomes
    a proper key-to-user lookup. Operators distribute the secret out-of-band.
    """
    settings = get_settings()
    if body.api_key != settings.factory_jwt_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    now = datetime.now(UTC)
    payload = {
        "sub": "factory-operator",
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expiration_minutes),
    }
    token = jwt.encode(payload, settings.factory_jwt_secret, algorithm=settings.jwt_algorithm)
    logger.info("factory_token_issued", sub="factory-operator")
    return TokenResponse(access_token=token, expires_in_minutes=settings.jwt_expiration_minutes)
```

**A4. Wire auth into the factory router**

In `factory/api/__init__.py`, add the auth router and apply the `verify_factory_token` dependency to all non-health routes:

```python
"""Factory API router — aggregates all v1 sub-routers."""

from fastapi import APIRouter, Depends

from factory.api.analyst import router as analyst_router
from factory.api.auth import router as auth_router
from factory.api.builds import router as builds_router
from factory.api.commissions import router as commissions_router
from factory.api.deployments import router as deployments_router
from factory.api.health import router as health_router
from factory.api.monitoring import router as monitoring_router
from factory.api.roster import router as roster_router
from factory.api.updates import router as updates_router
from factory.auth import verify_factory_token

api_router = APIRouter(prefix="/api/v1")

# Health is public — no auth
api_router.include_router(health_router)

# Token issuance is public — clients need this to get a token
api_router.include_router(auth_router)

# Everything else requires a valid JWT
_protected = APIRouter(dependencies=[Depends(verify_factory_token)])
_protected.include_router(analyst_router)
_protected.include_router(commissions_router)
_protected.include_router(builds_router)
_protected.include_router(deployments_router)
_protected.include_router(monitoring_router)
_protected.include_router(roster_router)
_protected.include_router(updates_router)

api_router.include_router(_protected)
```

---

### Part B — Employee runtime API auth

The employee runtime is simpler. It uses a single `EMPLOYEE_API_KEY` environment variable rather than a full JWT stack (employees are accessed by operators and the portal, not arbitrary clients).

**B1. Create `employee_runtime/core/auth.py`:**

```python
"""Employee runtime API authentication."""

from __future__ import annotations

import os
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = structlog.get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)

_DEFAULT_KEYS = {"", "forge-dev-key", "dev", "change-me"}


def _get_api_key() -> str:
    return os.environ.get("EMPLOYEE_API_KEY", "")


def _is_production() -> bool:
    return os.environ.get("ENVIRONMENT", "development") == "production"


async def verify_employee_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
) -> str:
    """Validate bearer API key for employee runtime endpoints."""
    api_key = _get_api_key()

    # In dev with no key set, allow all — makes local testing easier
    if not api_key and not _is_production():
        return "dev-passthrough"

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if credentials.credentials != api_key:
        logger.warning("employee_auth_failed", path=str(request.url.path))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
    return credentials.credentials


EmployeeAuth = Annotated[str, Depends(verify_employee_token)]
```

**B2. Wire auth into `employee_runtime/core/api.py`**

At the top of `employee_runtime/core/api.py`, import the dependency:

```python
from employee_runtime.core.auth import verify_employee_token
```

For every route that is NOT `/health` and NOT `/api/v1/health` and NOT `/api/v1/ws` (websocket), add `dependencies=[Depends(verify_employee_token)]` to the route decorator, OR add it once to the FastAPI app as a global dependency with path exclusions.

The cleanest approach for the employee app is to add it as an app-level middleware that skips the two health paths and the WebSocket path:

In `employee_runtime/core/api.py`, find where `app = FastAPI(...)` is created and add after it:

```python
from fastapi import Request
from fastapi.responses import JSONResponse
from employee_runtime.core.auth import _bearer, _get_api_key, _is_production

_UNPROTECTED_PATHS = {"/health", "/api/v1/health"}

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Enforce bearer auth on all paths except health checks."""
    if request.url.path in _UNPROTECTED_PATHS or request.url.path.startswith("/api/v1/ws"):
        return await call_next(request)
    api_key = _get_api_key()
    if not api_key and not _is_production():
        return await call_next(request)
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing bearer token"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header[7:]
    if token != api_key:
        return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
    return await call_next(request)
```

**B3. Startup guard for production**

In `employee_runtime/core/api.py`, in the lifespan startup block (find `@asynccontextmanager async def lifespan`), add:

```python
    # Refuse to start in production with no API key set
    _ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")
    _EMPLOYEE_API_KEY = os.environ.get("EMPLOYEE_API_KEY", "")
    if _ENVIRONMENT == "production" and not _EMPLOYEE_API_KEY:
        raise RuntimeError(
            "EMPLOYEE_API_KEY must be set in production. "
            "Generate one: python -c \"import secrets; print(secrets.token_hex(32))\""
        )
```

---

### Verify the auth layer works end-to-end

```bash
# Bring up the factory
docker compose up -d factory

# 1. Health must still be accessible without auth
curl -sf http://localhost:8000/api/v1/health
# Must return {"status":"ok",...}

# 2. Protected endpoint without token must return 401
curl -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/builds
# Must print 401

# 3. Get a token
TOKEN=$(curl -sf -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"api_key\": \"$(grep FACTORY_JWT_SECRET .env | cut -d= -f2)\"}" \
  | jq -r .access_token)
echo "TOKEN: ${TOKEN:0:20}..."

# 4. Protected endpoint WITH token must succeed
curl -sf -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/builds | jq length
# Must return a number (0 is fine), not 401

# 5. Expired/garbage token must return 401
curl -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer garbage.token.here" \
  http://localhost:8000/api/v1/builds
# Must print 401

# 6. Verify the factory portal can still reach the factory (CORS + auth must both work)
# Open the factory portal in a browser and confirm it loads data without 401 errors in console
```

---

### Commit message

```
feat: bearer token auth on factory and employee runtime APIs

- factory/auth.py: JWT verification dependency using pyjwt + factory_jwt_secret
- factory/api/auth.py: POST /api/v1/auth/token issues short-lived JWTs
- factory/api/__init__.py: all routes except /health and /auth/token now require JWT
- factory/main.py: refuse to start in production with default JWT secret
- employee_runtime/core/auth.py: bearer API key verification
- employee_runtime/core/api.py: HTTP middleware enforces auth on all non-health paths,
  startup guard refuses production boot with no EMPLOYEE_API_KEY
```

### Session summary

Print at end:

| Check | Status |
|---|---|
| `/health` accessible without token | ✅/❌ |
| Protected route returns 401 without token | ✅/❌ |
| Token issued successfully | ✅/❌ |
| Protected route returns 200 with token | ✅/❌ |
| Garbage token returns 401 | ✅/❌ |
| Factory still boots in development mode | ✅/❌ |

Do NOT add OAuth, RBAC, Clerk, or any other auth system. V1 is bearer tokens only.

---
---

## SESSION 3 — Silent Fallbacks (Days 9–10)
### Make degraded modes visible instead of invisible

**Goal:** Every component that silently degrades to a fallback mode must now (a) log a WARNING when the fallback activates, (b) return `healthy=False` from `health_check()` when operating in fallback, and (c) respect a `FORGE_STRICT_PROVIDERS=true` env flag that causes initialization to raise rather than degrade. This converts invisible production failures into loud, diagnosable signals.

---

Read these files first:

1. `factory/config.py` — understand FactorySettings structure so you can add `forge_strict_providers`
2. `component_library/tools/search_tool.py` — uses `fixture` mode when no Tavily key
3. `component_library/tools/document_ingestion.py` — uses text-split fallback when `unstructured` not installed
4. `component_library/tools/file_storage_tool.py` — uses `local` mode when no S3 credentials
5. `component_library/data/knowledge_base.py` — uses deterministic SHA hash when embedder unavailable
6. `component_library/quality/input_protection.py` lines 86–93 — already logs fallback (look at existing pattern and extend it)
7. `component_library/interfaces.py` — see `ComponentHealth` model

The `input_protection` component already has the right pattern — it logs `"input_protection_regex_fallback"` and sets `self._mode`. Use this as the template for every other component.

---

### Part A — Add `forge_strict_providers` to `FactorySettings`

In `factory/config.py`, add this field to `FactorySettings` after the `composio_api_key` field:

```python
    forge_strict_providers: bool = Field(
        False,
        description=(
            "When True, components raise ComponentInitializationError instead of "
            "silently degrading to fallback mode. Set True in staging/production."
        ),
    )
```

---

### Part B — Create a shared `ComponentInitializationError`

In `component_library/interfaces.py`, add at the bottom of the file:

```python
class ComponentInitializationError(RuntimeError):
    """Raised when a component cannot initialize its real provider and strict mode is on."""
```

---

### Part C — Apply the pattern to each fallback component

For each component below, apply all three changes:
1. **Log a WARNING** when fallback activates (use structlog: `logger.warning("component_fallback_active", component=..., reason=...)`)
2. **Set `self._fallback_active = True`** during initialize when the real provider isn't available
3. **In `health_check()`**, return `ComponentHealth(healthy=False, detail="fallback_mode: <reason>")` when `self._fallback_active` is True
4. **If `forge_strict_providers=True`** in settings, `raise ComponentInitializationError(...)` instead of degrading

Apply this to all five components:

#### `component_library/tools/search_tool.py`

In `initialize()`, after computing `mode`:
```python
        self._fallback_active = not bool(self._api_key)
        if self._fallback_active:
            logger.warning(
                "component_fallback_active",
                component="search_tool",
                reason="TAVILY_API_KEY not set; using fixture results",
            )
            from factory.config import get_settings
            if get_settings().forge_strict_providers:
                from component_library.interfaces import ComponentInitializationError
                raise ComponentInitializationError(
                    "search_tool: TAVILY_API_KEY required when FORGE_STRICT_PROVIDERS=true"
                )
```

In `health_check()`:
```python
    async def health_check(self) -> ComponentHealth:
        if self._fallback_active:
            return ComponentHealth(healthy=False, detail="fallback_mode: no TAVILY_API_KEY; returning fixtures")
        mode = "tavily"
        return ComponentHealth(healthy=True, detail=f"provider={self._provider}; mode={mode}")
```

#### `component_library/tools/document_ingestion.py`

In `initialize()`:
```python
        self._fallback_active = partition is None
        if self._fallback_active:
            logger.warning(
                "component_fallback_active",
                component="document_ingestion",
                reason="unstructured not installed; using naive text splitting",
            )
            from factory.config import get_settings
            if get_settings().forge_strict_providers:
                from component_library.interfaces import ComponentInitializationError
                raise ComponentInitializationError(
                    "document_ingestion: unstructured required when FORGE_STRICT_PROVIDERS=true. "
                    "Install with: pip install 'unstructured[all-docs]'"
                )
```

In `health_check()`:
```python
    async def health_check(self) -> ComponentHealth:
        if self._fallback_active:
            return ComponentHealth(
                healthy=False,
                detail="fallback_mode: unstructured not installed; using naive text split",
            )
        return ComponentHealth(healthy=True, detail="provider=unstructured")
```

#### `component_library/tools/file_storage_tool.py`

In `initialize()`, after setting `self._s3_client`:
```python
        self._fallback_active = (self._provider == "s3" and self._s3_client is None)
        if self._fallback_active:
            logger.warning(
                "component_fallback_active",
                component="file_storage_tool",
                reason="S3 provider requested but boto3 not installed or credentials missing; using local storage",
            )
            from factory.config import get_settings
            if get_settings().forge_strict_providers:
                from component_library.interfaces import ComponentInitializationError
                raise ComponentInitializationError(
                    "file_storage_tool: boto3 and S3 credentials required when FORGE_STRICT_PROVIDERS=true"
                )
```

In `health_check()`:
```python
    async def health_check(self) -> ComponentHealth:
        if self._fallback_active:
            return ComponentHealth(
                healthy=False,
                detail="fallback_mode: s3 requested but boto3 unavailable; using local filesystem",
            )
        mode = "s3" if self._s3_client is not None else self._provider
        return ComponentHealth(healthy=True, detail=f"provider={mode}; tenant={self._tenant_id}")
```

#### `component_library/data/knowledge_base.py`

Find where `self._allow_deterministic_fallback` is used. Add:

```python
        self._fallback_active = False
        if self._embedder is None and self._router is None:
            self._fallback_active = True
            logger.warning(
                "component_fallback_active",
                component="knowledge_base",
                reason="no embedder and no router; queries will return empty results",
            )
            from factory.config import get_settings
            if get_settings().forge_strict_providers:
                from component_library.interfaces import ComponentInitializationError
                raise ComponentInitializationError(
                    "knowledge_base: embedder or litellm_router required when FORGE_STRICT_PROVIDERS=true"
                )
```

Also, in the `_embed` or embedding path: when `allow_deterministic_fallback=True` is used, add:

```python
        logger.warning(
            "component_fallback_active",
            component="knowledge_base",
            reason="deterministic SHA-based embedding fallback active; retrieval quality is degraded",
        )
        self._fallback_active = True
```

In `health_check()`, update:
```python
    async def health_check(self) -> ComponentHealth:
        if self._fallback_active:
            return ComponentHealth(
                healthy=False,
                detail="fallback_mode: no real embedder; retrieval quality degraded",
            )
        storage = "database" if self._session_factory is not None else "memory"
        embedder_mode = "custom" if self._embedder is not None else "litellm_router"
        return ComponentHealth(
            healthy=True,
            detail=f"tenant={self._tenant_id}; storage={storage}; embedder={embedder_mode}",
        )
```

---

### Part D — Fix the activator integration polling loop

In `factory/pipeline/deployer/activator.py`, find:

```python
            await asyncio.sleep(0.01)
```

Replace with exponential backoff that is sane for production:

```python
            _poll_interval = min(5.0, 0.5 * (2 ** min(poll_attempt, 6)))
            poll_attempt += 1
            await asyncio.sleep(_poll_interval)
```

You will need to add `poll_attempt = 0` before the `while` loop.

This changes integration polling from 100 req/s to a 0.5s → 1s → 2s → 4s → 5s cap backoff — still responsive but not a denial-of-service against the integration provider.

---

### Verify

```bash
# Confirm components test suite still passes (the changes must not break tests)
pytest tests/components/ -q --tb=short 2>&1 | tail -10

# Spot-check: with no TAVILY_API_KEY, search_tool health_check should return healthy=False
python -c "
import asyncio
from component_library.tools.search_tool import SearchTool
async def test():
    s = SearchTool()
    await s.initialize({})  # No api_key
    h = await s.health_check()
    print('healthy:', h.healthy, '| detail:', h.detail)
    assert not h.healthy, 'Expected healthy=False in fallback mode'
    print('PASS')
asyncio.run(test())
"

# Spot-check: strict mode raises instead of degrading
python -c "
import os
os.environ['FORGE_STRICT_PROVIDERS'] = 'true'
import asyncio
from factory.config import get_settings
get_settings.cache_clear()
from component_library.tools.search_tool import SearchTool
from component_library.interfaces import ComponentInitializationError
async def test():
    s = SearchTool()
    try:
        await s.initialize({})
        print('FAIL — should have raised')
    except ComponentInitializationError as e:
        print('PASS — raised ComponentInitializationError:', e)
asyncio.run(test())
"
```

---

### Commit message

```
feat: loud fallbacks — unhealthy health_check and FORGE_STRICT_PROVIDERS flag

- Add forge_strict_providers: bool to FactorySettings (default False)
- Add ComponentInitializationError to component_library/interfaces.py
- search_tool: healthy=False + WARNING log when TAVILY_API_KEY unset
- document_ingestion: healthy=False + WARNING log when unstructured not installed
- file_storage_tool: healthy=False + WARNING log when S3 requested but boto3 unavailable
- knowledge_base: healthy=False + WARNING log when no embedder and deterministic fallback fires
- All four: raise ComponentInitializationError when FORGE_STRICT_PROVIDERS=true
- activator.py: replace asyncio.sleep(0.01) hot loop with exponential backoff (cap 5s)
```

### Session summary

Print at end:

| Component | health_check in fallback | strict mode raises | Test suite |
|---|---|---|---|
| search_tool | ✅/❌ | ✅/❌ | |
| document_ingestion | ✅/❌ | ✅/❌ | |
| file_storage_tool | ✅/❌ | ✅/❌ | |
| knowledge_base | ✅/❌ | ✅/❌ | |
| tests/components/ overall | | | X/114 |

---
---

## SESSION 4 — Component Schema Enrichment + LLM Architect Default (Exam Week 1-A)
### Make the component registry machine-readable and flip the architect to LLM-first

**Goal:** `describe_all_components()` currently returns `config_schema_json="{}"` for every component. The LLM architect cannot reason about component configuration with empty schemas. This session adds real config schemas to every production component as a class attribute, updates the registry to emit them, and flips `use_llm_architect` from `False` to `True` as the default.

---

Read these files first:

1. `component_library/registry.py` — see `describe_all_components()` and `config_schema_json=json.dumps({}, sort_keys=True)` on line ~61
2. `component_library/interfaces.py` — see `BaseComponent` — you will add `config_schema: ClassVar[dict]` here
3. `component_library/models/litellm_router.py` lines 114–140 — see what config keys `initialize()` reads
4. `component_library/data/knowledge_base.py` `initialize()` — config keys
5. `component_library/quality/input_protection.py` `initialize()` — config keys
6. `component_library/tools/email_tool.py` `initialize()` — config keys
7. `component_library/tools/search_tool.py` `initialize()` — config keys
8. `factory/pipeline/architect/prompts/component_selection.md` — the prompt the LLM architect uses; update it after adding schemas
9. `factory/config.py` — find `use_llm_architect: bool = Field(False)` to change default

---

### Part A — Add `config_schema` class attribute to `BaseComponent`

In `component_library/interfaces.py`, add `ClassVar` import and the class attribute:

```python
from typing import Any, ClassVar
```

In `BaseComponent`:

```python
class BaseComponent(ABC):
    component_id: str
    version: str
    category: str

    # Override in each component with the config keys initialize() accepts.
    # Each key maps to: {"type": str, "required": bool, "description": str, "default": Any}
    config_schema: ClassVar[dict[str, dict[str, object]]] = {}
```

### Part B — Update registry to emit real schemas

In `component_library/registry.py`, replace:

```python
                config_schema_json=json.dumps({}, sort_keys=True),
```

With:

```python
                config_schema_json=json.dumps(
                    getattr(cls, "config_schema", {}), sort_keys=True, default=str
                ),
```

### Part C — Add `config_schema` to every production component

For each component, read its `initialize()` method to find what config keys it reads, then add a `config_schema` class attribute above `component_id`. Here is the full set to implement:

**`component_library/models/litellm_router.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "primary_model": {"type": "str", "required": True, "description": "Primary LLM model string (e.g. openrouter/anthropic/claude-3.5-sonnet)", "default": ""},
        "fallback_model": {"type": "str", "required": False, "description": "Fallback model if primary fails", "default": ""},
        "reasoning_model": {"type": "str", "required": False, "description": "Model for deep reasoning tasks (o4-mini class)", "default": ""},
        "safety_model": {"type": "str", "required": False, "description": "Fast model for safety/guardrail checks", "default": ""},
        "fast_model": {"type": "str", "required": False, "description": "Latency-optimized model for simple tasks", "default": ""},
        "embedding_model": {"type": "str", "required": False, "description": "Model for vector embeddings", "default": "openai/text-embedding-3-large"},
        "max_tokens": {"type": "int", "required": False, "description": "Default max output tokens per call", "default": 4096},
        "timeout": {"type": "int", "required": False, "description": "Request timeout in seconds", "default": 60},
    }
```

**`component_library/data/knowledge_base.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "tenant_id": {"type": "str", "required": True, "description": "UUID scoping all stored knowledge to one tenant", "default": ""},
        "session_factory": {"type": "object", "required": False, "description": "SQLAlchemy async_sessionmaker for pgvector persistence; omit for in-memory", "default": None},
        "embedding_model": {"type": "str", "required": False, "description": "litellm embedding model string", "default": "openai/text-embedding-3-large"},
        "allow_deterministic_fallback": {"type": "bool", "required": False, "description": "Allow SHA-based fake embeddings when real embedder unavailable (dev only)", "default": False},
    }
```

**`component_library/tools/search_tool.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "tavily_api_key": {"type": "str", "required": False, "description": "Tavily API key; omit to use local fixtures (dev only)", "default": ""},
        "max_results": {"type": "int", "required": False, "description": "Maximum search results to return", "default": 5},
        "rate_limit_seconds": {"type": "float", "required": False, "description": "Minimum seconds between Tavily calls", "default": 0.0},
    }
```

**`component_library/tools/email_tool.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "composio_api_key": {"type": "str", "required": False, "description": "Composio API key for Gmail/Outlook integration", "default": ""},
        "provider": {"type": "str", "required": False, "description": "Email provider: gmail | outlook | memory (dev)", "default": "memory"},
        "tenant_id": {"type": "str", "required": False, "description": "Tenant scoping for email isolation", "default": "default-tenant"},
    }
```

**`component_library/tools/file_storage_tool.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "provider": {"type": "str", "required": False, "description": "Storage backend: s3 | local | memory", "default": "local"},
        "bucket": {"type": "str", "required": False, "description": "S3/MinIO bucket name", "default": "forge-artifacts"},
        "endpoint_url": {"type": "str", "required": False, "description": "S3-compatible endpoint (e.g. http://minio:9000)", "default": ""},
        "tenant_id": {"type": "str", "required": False, "description": "Tenant prefix for storage isolation", "default": "default-tenant"},
    }
```

**`component_library/tools/document_ingestion.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "provider": {"type": "str", "required": False, "description": "Parsing backend: unstructured | local (naive text split)", "default": "local"},
    }
```

**`component_library/quality/input_protection.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "injection_threshold": {"type": "float", "required": False, "description": "Confidence threshold for prompt injection detection (0.0–1.0)", "default": 0.8},
        "pii_detection": {"type": "bool", "required": False, "description": "Enable PII detection via Guardrails", "default": True},
        "toxicity_detection": {"type": "bool", "required": False, "description": "Enable toxicity screening", "default": True},
    }
```

**`component_library/quality/autonomy_manager.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "default_autonomy_level": {"type": "str", "required": False, "description": "full_auto | supervised | approval_required | manual", "default": "supervised"},
        "high_risk_threshold": {"type": "float", "required": False, "description": "Confidence below which HIGH-risk actions require approval", "default": 0.85},
        "critical_risk_threshold": {"type": "float", "required": False, "description": "Confidence below which CRITICAL actions always escalate", "default": 0.95},
    }
```

**`component_library/quality/compliance_rules.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "opa_url": {"type": "str", "required": False, "description": "OPA server URL (e.g. http://localhost:8181); omit for regex fallback", "default": ""},
        "policy_package": {"type": "str", "required": False, "description": "OPA policy package path (e.g. forge/legal)", "default": "forge/legal"},
    }
```

**`component_library/quality/adversarial_review.py`:**
```python
    config_schema: ClassVar[dict[str, dict[str, object]]] = {
        "deliberation_council": {"type": "object", "required": False, "description": "CouncilConfig overrides; see DeliberationCouncil for full schema", "default": {}},
    }
```

For every other production component not listed above (`text_processor`, `document_analyzer`, `draft_generator`, `communication_manager`, `scheduler_manager`, `workflow_executor`, `data_analyzer`, `research_engine`, `monitor_scanner`, `calendar_tool`, `messaging_tool`, `crm_tool`, `custom_api_tool`, `operational_memory`, `working_memory`, `context_assembler`, `org_context`, `confidence_scorer`, `audit_system`, `verification_layer`, `explainability`, `approval_manager`, `anthropic_provider`): read each component's `initialize()` method and add a real `config_schema` with at minimum the keys that `initialize()` actually reads from config.

### Part D — Update the architect prompt

In `factory/pipeline/architect/prompts/component_selection.md`, after the existing content, add a section that tells the LLM what schemas are available:

```markdown

The component catalog JSON provided as input now includes `config_schema_json` for each component.
This is a JSON object where each key is a config parameter, with:
- `type`: Python type name
- `required`: whether the component needs this key to function
- `description`: what the parameter controls
- `default`: value used when omitted

When generating the `config` object for each selected component, use the schema to populate
appropriate values. Required fields must always be set. Optional fields should be set when
the employee requirements specify relevant constraints (e.g. if requirements mention a specific
model preference, set `primary_model` accordingly).
```

### Part E — Flip `use_llm_architect` default to True

In `factory/config.py`, find:

```python
    use_llm_architect: bool = Field(False)
```

Change to:

```python
    use_llm_architect: bool = Field(
        True,
        description=(
            "Use LLM-driven component selection (True) or rule-based fallback (False). "
            "Defaults True — Forge is a factory, Architect should be autonomous. "
            "Set False only if LLM calls are unavailable or for deterministic testing."
        ),
    )
```

---

### Verify

```bash
# Registry now returns real schemas
python -c "
from component_library.registry import describe_all_components
import json
descs = describe_all_components()
empty = [d.component_id for d in descs if d.config_schema_json == '{}']
print(f'Components with empty schema: {empty}')
assert not empty, 'All production components must have non-empty config_schema'
print(f'PASS: {len(descs)} components, all with real schemas')
"

# Component tests still pass
pytest tests/components/ -q --tb=no 2>&1 | tail -3
```

---

### Commit message

```
feat: real component config schemas; LLM architect on by default

- BaseComponent.config_schema ClassVar added to interfaces.py
- registry.py emits real config_schema_json from class attribute
- All 28 production components have real config_schema dicts
- architect prompt updated to instruct LLM to use schemas when building config
- use_llm_architect default changed from False to True
```

---
---

## SESSION 5 — Task State Machine (Exam Week 1-B)
### Enforce legal task state transitions in one place

**Goal:** `task_repository.py`'s `update_task()` accepts arbitrary `changes` dicts, meaning a bug in calling code can set any status regardless of what the current status is. A `TaskStateMachine` class with an explicit transition table makes illegal transitions impossible and is the foundation for reliable long-lived employee operation.

---

Read these files first:

1. `employee_runtime/core/task_repository.py` — full file; understand the `update_task` signature and implementation in both `InMemoryTaskRepository` and `SqlAlchemyTaskRepository`
2. `factory/models/orm.py` lines 435–495 — see `EmployeeTaskRow` and its `status` field; note the valid status strings in the column definition if any
3. `tests/runtime/test_task_recovery.py` — understand how tasks are created and transitioned in tests; your new machine must not break these

---

### Part A — Create `employee_runtime/core/task_state_machine.py`

```python
"""Task state machine — enforces legal lifecycle transitions for employee tasks.

Valid statuses and their legal successors:

  queued           → running
  running          → completed | failed | awaiting_approval | interrupted
  awaiting_approval → running | failed
  interrupted      → queued   (retry after restart)
  completed        → (terminal — no transitions out)
  failed           → queued   (explicit retry only)

Any other transition raises InvalidTaskTransition.
"""

from __future__ import annotations


class InvalidTaskTransition(ValueError):
    """Raised when a requested status transition is not permitted."""


# Map: current_status → set of statuses it can transition to
_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued":             frozenset({"running"}),
    "running":            frozenset({"completed", "failed", "awaiting_approval", "interrupted"}),
    "awaiting_approval":  frozenset({"running", "failed"}),
    "interrupted":        frozenset({"queued"}),
    "completed":          frozenset(),          # terminal
    "failed":             frozenset({"queued"}),  # explicit retry only
}

ALL_STATUSES: frozenset[str] = frozenset(_TRANSITIONS.keys())

INFLIGHT_STATUSES: frozenset[str] = frozenset({"queued", "running", "awaiting_approval"})

TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed"})


class TaskStateMachine:
    """Validates task status transitions.

    Usage:
        machine = TaskStateMachine()
        machine.validate("running", "completed")  # OK
        machine.validate("completed", "running")  # raises InvalidTaskTransition
    """

    def validate(self, current_status: str, new_status: str) -> None:
        """Assert that transitioning from current_status to new_status is legal.

        Args:
            current_status: The task's current status string.
            new_status: The desired next status string.

        Raises:
            InvalidTaskTransition: If the transition is not permitted.
            ValueError: If either status is not a recognised status string.
        """
        if current_status not in _TRANSITIONS:
            raise ValueError(
                f"Unknown current status '{current_status}'. Valid: {sorted(ALL_STATUSES)}"
            )
        if new_status not in _TRANSITIONS:
            raise ValueError(
                f"Unknown target status '{new_status}'. Valid: {sorted(ALL_STATUSES)}"
            )
        allowed = _TRANSITIONS[current_status]
        if new_status not in allowed:
            raise InvalidTaskTransition(
                f"Cannot transition task from '{current_status}' to '{new_status}'. "
                f"Allowed from '{current_status}': {sorted(allowed) or '(terminal)'}"
            )

    def is_terminal(self, status: str) -> bool:
        return status in TERMINAL_STATUSES

    def is_inflight(self, status: str) -> bool:
        return status in INFLIGHT_STATUSES
```

### Part B — Wire into `task_repository.py`

At the top of `employee_runtime/core/task_repository.py`, add:

```python
from employee_runtime.core.task_state_machine import InvalidTaskTransition, TaskStateMachine

_state_machine = TaskStateMachine()
```

Also replace the existing `INFLIGHT_TASK_STATUSES` constant (if present) with:

```python
from employee_runtime.core.task_state_machine import INFLIGHT_STATUSES as INFLIGHT_TASK_STATUSES
```

In `InMemoryTaskRepository.update_task()`, before applying the changes dict, add the guard:

```python
        task = self._store.get(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found")
        if "status" in changes:
            _state_machine.validate(str(task.get("status", "queued")), str(changes["status"]))
```

In `SqlAlchemyTaskRepository.update_task()`, inside the async session block, before applying updates to the row, add:

```python
            if "status" in changes:
                _state_machine.validate(str(row.status), str(changes["status"]))
```

The reconciliation path that sets `interrupted` on startup writes directly without calling `update_task` — leave that path alone (it's an administrative override that bypasses normal flow intentionally). Add a comment marking it:

```python
            row.status = "interrupted"  # Administrative override — bypasses state machine intentionally
```

### Part C — Add a test for the state machine

Create `tests/runtime/test_task_state_machine.py`:

```python
"""Unit tests for TaskStateMachine."""
import pytest
from employee_runtime.core.task_state_machine import (
    InvalidTaskTransition,
    TaskStateMachine,
)

machine = TaskStateMachine()


def test_legal_transitions():
    machine.validate("queued", "running")
    machine.validate("running", "completed")
    machine.validate("running", "failed")
    machine.validate("running", "awaiting_approval")
    machine.validate("running", "interrupted")
    machine.validate("awaiting_approval", "running")
    machine.validate("awaiting_approval", "failed")
    machine.validate("interrupted", "queued")
    machine.validate("failed", "queued")


def test_illegal_transitions_raise():
    with pytest.raises(InvalidTaskTransition):
        machine.validate("completed", "running")
    with pytest.raises(InvalidTaskTransition):
        machine.validate("completed", "failed")
    with pytest.raises(InvalidTaskTransition):
        machine.validate("failed", "running")
    with pytest.raises(InvalidTaskTransition):
        machine.validate("queued", "completed")


def test_terminal_statuses():
    assert machine.is_terminal("completed")
    assert machine.is_terminal("failed")
    assert not machine.is_terminal("running")
    assert not machine.is_terminal("queued")


def test_inflight_statuses():
    assert machine.is_inflight("queued")
    assert machine.is_inflight("running")
    assert machine.is_inflight("awaiting_approval")
    assert not machine.is_inflight("completed")
    assert not machine.is_inflight("interrupted")


def test_unknown_status_raises():
    with pytest.raises(ValueError, match="Unknown"):
        machine.validate("not_a_real_status", "running")
```

---

### Verify

```bash
pytest tests/runtime/test_task_state_machine.py -v 2>&1 | tail -20
# All tests must pass

pytest tests/runtime/ -q --tb=short 2>&1 | tail -10
# No regressions in existing runtime tests

pytest tests/components/ -q --tb=no 2>&1 | tail -3
# Still 114 passed
```

---

### Commit message

```
feat: TaskStateMachine enforces legal task lifecycle transitions

- employee_runtime/core/task_state_machine.py: explicit transition table,
  InvalidTaskTransition exception, is_terminal/is_inflight helpers
- task_repository.py: InMemory and SqlAlchemy implementations validate
  status changes through the machine before applying them
- tests/runtime/test_task_state_machine.py: legal/illegal transition coverage
```

---
---

## SESSION 6 — Split Health Endpoint (Exam Week 1-C)
### Separate liveness, readiness, and recovery into distinct endpoints

**Goal:** The current `/health` and `/api/v1/health` return `{"status":"ok"}` regardless of whether the database is reachable or whether tasks were interrupted on last restart. Monitoring systems, load balancers, and the factory's `activator.py` need to distinguish "process is alive" from "dependencies are ready" from "what needs recovery." This session splits one shallow check into three honest ones.

---

Read these files first:

1. `factory/api/health.py` — the current shallow health endpoint
2. `factory/database.py` — `get_engine()`, `get_session_factory()` for DB ping
3. `factory/config.py` — `get_settings()` for Redis URL, OPA URL context
4. `employee_runtime/core/api.py` — find both health endpoints (`/health` and `/api/v1/health`) and the lifespan startup
5. `employee_runtime/core/task_repository.py` — `get_interrupted_tasks()` or equivalent method for recovery data

---

### Part A — Factory: split `factory/api/health.py`

Replace the entire file contents with:

```python
"""Factory health, readiness, and recovery endpoints."""

from __future__ import annotations

import asyncio

import httpx
import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from factory.config import get_settings
from factory.database import get_engine

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["meta"])


class LivenessResponse(BaseModel):
    status: str
    service: str
    version: str


class DependencyStatus(BaseModel):
    name: str
    healthy: bool
    detail: str = ""


class ReadinessResponse(BaseModel):
    ready: bool
    dependencies: list[DependencyStatus]


class RecoveryResponse(BaseModel):
    interrupted_builds: int
    detail: str = ""


@router.get("/health", response_model=LivenessResponse, summary="Process liveness")
async def liveness() -> LivenessResponse:
    """Returns 200 if the process is alive. Never checks dependencies.
    Use this for container restart policies and basic uptime monitoring."""
    return LivenessResponse(status="ok", service="forge-factory", version="0.2.0")


@router.get("/api/v1/health", response_model=LivenessResponse, summary="Process liveness (v1 alias)")
async def liveness_v1() -> LivenessResponse:
    """Alias of /health kept for backwards compatibility with the docker healthcheck."""
    return LivenessResponse(status="ok", service="forge-factory", version="0.2.0")


@router.get("/api/v1/ready", response_model=ReadinessResponse, summary="Dependency readiness")
async def readiness() -> ReadinessResponse:
    """Returns 200 only when all critical dependencies are reachable.
    Use this for load-balancer health gates and deployment validation."""
    settings = get_settings()
    deps: list[DependencyStatus] = []

    # Postgres
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        deps.append(DependencyStatus(name="postgres", healthy=True))
    except Exception as exc:
        deps.append(DependencyStatus(name="postgres", healthy=False, detail=str(exc)))

    # Redis
    try:
        client = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await client.ping()
        await client.aclose()
        deps.append(DependencyStatus(name="redis", healthy=True))
    except Exception as exc:
        deps.append(DependencyStatus(name="redis", healthy=False, detail=str(exc)))

    # OPA (optional — degrade gracefully if not configured)
    opa_url = "http://localhost:8181"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{opa_url}/health")
            deps.append(DependencyStatus(
                name="opa", healthy=resp.status_code == 200,
                detail="" if resp.status_code == 200 else f"status={resp.status_code}"
            ))
    except Exception as exc:
        deps.append(DependencyStatus(name="opa", healthy=False, detail=str(exc)))

    all_healthy = all(d.healthy for d in deps)
    return ReadinessResponse(ready=all_healthy, dependencies=deps)


@router.get("/api/v1/recovery", response_model=RecoveryResponse, summary="Recovery state")
async def recovery() -> RecoveryResponse:
    """Returns counts of work interrupted by the last restart.
    Use this to confirm the factory started cleanly after a crash."""
    try:
        from factory.database import get_session_factory
        from factory.models.orm import BuildRow
        from sqlalchemy import select
        session_factory = get_session_factory()
        async with session_factory() as session:
            result = await session.execute(
                select(BuildRow).where(BuildRow.status == "interrupted")
            )
            interrupted = result.scalars().all()
            return RecoveryResponse(
                interrupted_builds=len(interrupted),
                detail=f"interrupted build ids: {[str(b.id) for b in interrupted]}" if interrupted else "",
            )
    except Exception as exc:
        return RecoveryResponse(interrupted_builds=-1, detail=f"recovery check failed: {exc}")
```

Note: `redis.asyncio` requires `redis[asyncio]` — check if it's already in deps. If not, add `"redis[asyncio]>=5.0,<6"` to core deps in `pyproject.toml`. (SQLAlchemy and the existing stack likely already pull in redis; verify before adding.)

### Part B — Employee runtime: same split in `employee_runtime/core/api.py`

Find the existing `/health` and `/api/v1/health` endpoints. Keep both returning 200 always (liveness). Then add:

```python
@app.get("/api/v1/ready")
async def employee_readiness() -> dict[str, object]:
    """Check that the employee's critical dependencies are reachable."""
    results: dict[str, object] = {"ready": True, "dependencies": []}
    deps: list[dict[str, object]] = []

    # DB check
    try:
        from employee_runtime.core.runtime_db import get_runtime_session_factory
        sf = get_runtime_session_factory()
        if sf:
            from sqlalchemy import text
            async with sf() as session:
                await session.execute(text("SELECT 1"))
            deps.append({"name": "postgres", "healthy": True})
        else:
            deps.append({"name": "postgres", "healthy": False, "detail": "session_factory not initialised"})
    except Exception as exc:
        deps.append({"name": "postgres", "healthy": False, "detail": str(exc)})

    all_healthy = all(bool(d.get("healthy")) for d in deps)
    results["ready"] = all_healthy
    results["dependencies"] = deps
    return results


@app.get("/api/v1/recovery")
async def employee_recovery() -> dict[str, object]:
    """Return tasks that were interrupted by the last container restart."""
    try:
        task_repo = app.state.task_repository
        interrupted = await task_repo.get_interrupted_tasks(
            employee_id=app.state.identity.get("employee_id", "unknown")
        )
        return {
            "interrupted_tasks": len(interrupted),
            "task_ids": [t.get("task_id") for t in interrupted],
        }
    except Exception as exc:
        return {"interrupted_tasks": -1, "detail": str(exc)}
```

If `get_runtime_session_factory()` or `get_interrupted_tasks()` don't exist exactly as named, find the equivalent in the codebase and use those. Do not create new ones.

---

### Verify

```bash
# Bring up the full stack
docker compose up -d

# Liveness — always 200
curl -sf http://localhost:8000/health | jq .
curl -sf http://localhost:8000/api/v1/health | jq .

# Readiness — should show all dependencies green when stack is up
curl -sf http://localhost:8000/api/v1/ready | jq .
# Expect: {"ready": true, "dependencies": [{"name": "postgres", "healthy": true}, ...]}

# Recovery — should show 0 interrupted builds on clean start
curl -sf http://localhost:8000/api/v1/recovery | jq .
# Expect: {"interrupted_builds": 0, ...}

# Take postgres down and confirm /ready goes false
docker compose stop postgres
curl -sf http://localhost:8000/api/v1/ready | jq .
# Expect: {"ready": false, "dependencies": [{"name": "postgres", "healthy": false}, ...]}
# /health must still return 200 even with postgres down
curl -sf http://localhost:8000/health | jq .

# Bring postgres back
docker compose start postgres
```

---

### Commit message

```
feat: split health into /health (liveness), /ready (readiness), /recovery

- /health and /api/v1/health: process-only liveness, never checks deps
- /api/v1/ready: pings postgres, redis, opa; returns per-dependency status
- /api/v1/recovery: reports builds/tasks interrupted by last restart
- Same split applied to employee_runtime /api/v1/ready and /api/v1/recovery
```

---
---

## SESSION 7 — Deployment Proof (Exam Week 2-D)
### Prove the Docker Compose server export end-to-end against real infrastructure

**Goal:** Produce a real deployed employee via the server-export path. This is the deployment format most relevant for legal-vertical clients (self-hosted, data stays on-premises). Run the full path: factory commissions an employee → builds it → packages a Docker Compose handoff bundle → client-side `docker compose up` starts the employee → employee receives a real task and returns a real brief.

---

Read these files first:

1. `factory/pipeline/builder/packager.py` full file — understand how server bundles are produced
2. `factory/pipeline/deployer/providers/docker_compose_export.py` full file — understand the export provider
3. `employee_runtime/templates/docker-compose.template` — the template for the exported bundle
4. `employee_runtime/templates/Dockerfile.template` — the employee Dockerfile template
5. `tests/factory/test_pipeline/test_server_bundle_handoff.py` — existing test; understand what it proves
6. `factory/pipeline/deployer/activator.py` — understand how the factory activates a deployed employee
7. `tests/fixtures/sample_emails.py` — use `URGENT` as the test intake email

---

### What this session does

This is an integration/validation session, not primarily a code-writing session. The ratio is 80% running things, 20% fixing what breaks.

### Step 1 — Set up environment

Confirm these env vars are set before running anything:

```bash
echo "ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:+SET (${#ANTHROPIC_API_KEY} chars)}"
echo "OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:+SET}"
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:+SET}"
# At least one of ANTHROPIC or OPENROUTER must be set
```

Bring the full stack up:

```bash
docker compose up -d
sleep 10
curl -sf http://localhost:8000/api/v1/health
```

### Step 2 — Commission and build an employee via the factory API

```bash
API=http://localhost:8000/api/v1

# Get auth token
TOKEN=$(curl -sf -X POST $API/auth/token \
  -H "Content-Type: application/json" \
  -d "{\"api_key\": \"$(grep -E '^FACTORY_JWT_SECRET' .env 2>/dev/null | cut -d= -f2 || echo forge-factory-dev-secret)\"}" \
  | jq -r '.access_token // "no-token"')

AUTH="Authorization: Bearer $TOKEN"

# Start analyst session
SESSION=$(curl -sf -X POST $API/analyst/sessions \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{
    "org_id": "00000000-0000-0000-0000-000000000001",
    "initial_prompt": "We are Cartwright Law, a 10-attorney employment law firm. We receive 30 inbound intake emails per week and need them triaged and structured into intake briefs for partner review. Supervisor is partner Dana Cartwright. Tools: Gmail, Slack. Risk tier: HIGH — errors could cause malpractice exposure. We do not take class actions. Conflict check against a CSV list of current clients."
  }' | jq -r .session_id)

echo "SESSION=$SESSION"

# Feed 3 replies to reach completeness
for reply in \
  "Practice areas: wrongful termination, wage disputes, harassment. Conflict list is at /opt/conflicts.csv with columns party_name, matter_id, status." \
  "Urgency: flag any mention of statute of limitations, EEOC deadlines, or dates within 45 days. Alert Dana via Slack DM immediately." \
  "Approval required for any outbound email to a prospective client and for any ACCEPT qualification decision."; do
  curl -sf -X POST $API/analyst/sessions/$SESSION/messages \
    -H "Content-Type: application/json" \
    -H "$AUTH" \
    -d "{\"role\": \"user\", \"content\": $(echo "$reply" | jq -Rs .)}" | jq '.state.completeness_score // "?"'
done

# Commission the build — IMPORTANT: set deployment_mode to "server_export"
BUILD_ID=$(curl -sf -X POST $API/commissions \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d "{\"session_id\": \"$SESSION\", \"org_id\": \"00000000-0000-0000-0000-000000000001\", \"deployment_mode\": \"server_export\"}" \
  | jq -r .build_id)

echo "BUILD_ID=$BUILD_ID"
```

### Step 3 — Watch the build

```bash
# Poll every 20s, timeout after 25 minutes
for i in {1..75}; do
  STATUS=$(curl -sf -H "$AUTH" $API/builds/$BUILD_ID | jq -r .status)
  echo "[$(date +%H:%M:%S)] [$i/75] status=$STATUS"
  if [[ "$STATUS" == "deployed" || "$STATUS" == "failed" ]]; then break; fi
  sleep 20
done

# If failed, get the logs to understand what stage failed
if [[ "$STATUS" == "failed" ]]; then
  curl -sf -H "$AUTH" $API/builds/$BUILD_ID | jq '.logs[-10:]'
  echo "BUILD FAILED — see logs above. Stop and report."
  exit 1
fi
```

### Step 4 — Find and run the exported bundle

```bash
# Get the artifact path from build metadata
ARTIFACT_PATH=$(curl -sf -H "$AUTH" $API/builds/$BUILD_ID | jq -r '.metadata.artifact_path // empty')
echo "ARTIFACT_PATH=$ARTIFACT_PATH"

# The server export creates a tarball or directory. Find it.
ls -lh "$ARTIFACT_PATH" 2>/dev/null || find /tmp -name "*forge-employee*" -newer /tmp 2>/dev/null | head -5

# Extract if it's a tarball
BUNDLE_DIR="/tmp/forge-employee-bundle-test"
mkdir -p "$BUNDLE_DIR"
tar -xzf "$ARTIFACT_PATH" -C "$BUNDLE_DIR" 2>/dev/null || cp -r "$ARTIFACT_PATH"/* "$BUNDLE_DIR"/ 2>/dev/null || true

ls "$BUNDLE_DIR"
# Should contain: docker-compose.yml, Dockerfile or image ref, .env.example, employee_runtime/, etc.

# Bring up the employee
cd "$BUNDLE_DIR"
EMPLOYEE_API_KEY="test-employee-key-$(date +%s)" \
  docker compose up -d

sleep 15
EMPLOYEE_PORT=$(grep -oE ":[0-9]+:[0-9]+" docker-compose.yml | head -1 | cut -d: -f3)
EMPLOYEE_URL="http://localhost:${EMPLOYEE_PORT:-8080}"
echo "EMPLOYEE_URL=$EMPLOYEE_URL"

curl -sf $EMPLOYEE_URL/api/v1/health | jq .
```

### Step 5 — Send a real intake email and verify the brief

```bash
# Send the URGENT sample from tests/fixtures/sample_emails.py
TASK=$(curl -sf -X POST $EMPLOYEE_URL/api/v1/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test-employee-key-$(date +%s)" \
  -d '{
    "input": "Subject: URGENT - Statute of Limitations Expiring\n\nI was injured at my workplace 2 years and 11 months ago. I just learned that the statute of limitations for personal injury in our state is 3 years. That means I only have about 30 days to file. Please contact me IMMEDIATELY.\n\nMaria Garcia, (555) 222-3333, maria.garcia@email.com\nInjury: Chemical burn at Westfield Chemical plant on May 14, 2023",
    "input_type": "email"
  }')
TASK_ID=$(echo "$TASK" | jq -r .task_id)
echo "TASK_ID=$TASK_ID"

# Poll for completion
for i in {1..30}; do
  TASK_STATUS=$(curl -sf $EMPLOYEE_URL/api/v1/tasks/$TASK_ID | jq -r '.state // .status')
  echo "[$i] task=$TASK_STATUS"
  if [[ "$TASK_STATUS" == "completed" || "$TASK_STATUS" == "failed" || "$TASK_STATUS" == "awaiting_approval" ]]; then break; fi
  sleep 5
done

# Fetch the produced brief
curl -sf $EMPLOYEE_URL/api/v1/tasks/$TASK_ID/brief | jq . > /tmp/produced_brief.json
cat /tmp/produced_brief.json
```

### Step 6 — Prove sovereignty

```bash
# Stop the factory — employee must keep working
docker compose -f /path/to/repo/docker-compose.yml stop factory pipeline-worker
echo "Factory stopped. Employee should still respond:"
curl -sf $EMPLOYEE_URL/api/v1/health | jq .
# Must return 200

# Send another task with factory offline
TASK2=$(curl -sf -X POST $EMPLOYEE_URL/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "input": "Subject: Car Accident - Need Legal Help\n\nMy name is Sarah Johnson and I was in a car accident on February 15, 2026. The other driver ran a red light. I have $45,000 in medical bills. Phone: (555) 123-4567.",
    "input_type": "email"
  }')
echo "Task submitted while factory offline: $(echo $TASK2 | jq -r .task_id)"
# Must succeed — factory being offline must not affect the deployed employee
```

---

### What constitutes success for this session

All of these must be true:

1. Build reaches status `deployed` within 25 minutes
2. Exported bundle contains a valid `docker-compose.yml` that starts cleanly
3. Employee responds to `/api/v1/health` with 200
4. `URGENT` email produces a brief with `urgency_flag: true` and extracted contact info
5. Employee continues responding to requests after factory containers are stopped

If any step fails, document exactly which step, the error output, and the relevant log lines. Do NOT force-pass by mocking or patching. An honest failure report is more valuable than a fake success.

---

### Commit message

```
test: server export deployment proof — full e2e verified

- Document which pipeline stages ran and their durations
- Record produced brief from URGENT intake email
- Confirm sovereignty: employee functional with factory stopped
- Note any fixes made to packager/export/activator during the run
```

---
---

## SESSION 8 — Documentation Accuracy Audit (Exam Week 2-E)
### Make CLAUDE.md and README honest about what's real vs. roadmap

**Goal:** CLAUDE.md makes ambitious claims. Some are fully implemented, some are partially implemented, and some are future-state. Every claim must now be tagged accurately so that a law firm partner reading the docs before a pilot doesn't feel misled. This session is a read-then-edit pass: read each claim in CLAUDE.md, find the corresponding code, and update the claim or tag it.

---

Read these files first, all of them:

1. `CLAUDE.md` — the primary document to audit
2. `AGENTS.md` — secondary; check for analogous claim issues
3. `README.md` — public-facing; must be the most conservative
4. The gap matrix from the most recent audit session (it's in the repo or in your context)

---

### The tagging convention

Add one of these tags to every claim in CLAUDE.md that is not yet fully proven:

- `[Implemented]` — code exists, unit tested, behavior verified
- `[Implemented — not yet E2E proven]` — code exists and is correct, but no live end-to-end run has validated it against real infrastructure
- `[Partially implemented]` — core exists but specific sub-features are stubs or fallbacks
- `[Roadmap — Phase 2]` — explicitly future-state; do not imply current capability
- `[Roadmap — Phase 3]` — further future-state

Do not delete claims. Do not rewrite the product vision. Just tag honestly.

---

### The specific claims to audit and tag (based on the gap matrix)

Go through each of these and find the relevant claim in CLAUDE.md. Apply the correct tag:

**Claims that are `[Implemented]`:**
- Factory pipeline exists (analyst → architect → builder → evaluator → deployer → monitor)
- Component library with modular selection
- LangGraph-based employee runtime with stateful workflow execution
- Task persistence with startup reconciliation
- Deliberation Council with adversarial debate (advocate, challenger, adjudicator, supervisor)
- Behavior rule precedence (direct commands > portal rules > adaptive)
- Factory portal with commission flow, build tracker, roster, employee detail pages
- Employee app with conversation, inbox, memory browser, metrics, settings
- Docker Compose server export deployment path

**Claims that are `[Implemented — not yet E2E proven]`:**
- Full end-to-end: commission → build → deploy → real task → real brief (Phase 5 of test plan)
- Railway hosted deployment (provider exists, not validated live)
- Desktop (Electron) deployment (packaging code exists, live artifact not produced post-cleanup)

**Claims that are `[Partially implemented]`:**
- "Behaves like a human colleague across Slack/email/Teams/calendar" — runtime wired, but Composio integrations use `InMemoryComposioClient` in production
- "24-hour rhythm with overnight review, morning briefing" — pulse_engine.py implemented, not validated running unattended over real time
- Employee identity six-layer architecture — conceptually sound, not traceable one-to-one in runtime prompt assembly
- Monitoring observes health, drift, performance, anomalies — scaffolded, drift detection is thin

**Claims that are `[Roadmap — Phase 2]`:**
- Federated learning across client deployments
- Marketplace for employee types
- Autonomous update system with semantic versioning
- "Eventually become superhuman" capability progression

**Claims that are `[Roadmap — Phase 3]`:**
- Air-gapped deployment
- Multi-language support
- Cross-vertical generalization beyond legal

---

### Part B — README.md update

README.md is public-facing and should be the most conservative. Specifically:

1. Add a section `## Current Status` near the top with an honest one-paragraph description of what Forge is today vs. the full vision.
2. Replace any bullet points that imply current capability for Roadmap items with `(planned)` or `(Phase 2)` notes.
3. Do NOT remove the ambitious vision — just distinguish it from current capability.

---

### Part C — Add a `KNOWN_GAPS.md` to repo root

Create `KNOWN_GAPS.md`:

```markdown
# Forge — Known Gaps (Last updated: [date])

This document lists gaps between Forge's documented capabilities and its current proven behavior.
It is updated after each major audit or test session.

## P0 — Must resolve before external pilot

- [ ] Full end-to-end pipeline run on live infrastructure (Phase 5 of FORGE_TEST_PLAN.md) never completed successfully
- [ ] No live client data has ever been processed by a deployed Forge employee
- [ ] Railway hosted deployment not yet validated against real Railway API
- [ ] `InMemoryComposioClient` used in production code path for tool integrations

## P1 — Must resolve before broad pilot

- [ ] Desktop (Electron) build artifacts need re-generation and signing after dist/ purge
- [ ] Employee 24-hour rhythm (pulse_engine) not validated running unattended
- [ ] Six-layer identity architecture not traceable one-to-one in runtime prompt assembly

## P2 — Target after alpha

- [ ] Monitoring drift detection is thin — scaffolded but not producing actionable signals
- [ ] Update system lifecycle not proven end-to-end
- [ ] Federated learning: Phase 2 roadmap only

## Resolved

- [x] OPA Rego syntax error in legal.rego — fixed in hardening pass
- [x] email-validator missing from factory image — fixed in hardening pass
- [x] 728MB committed Electron artifacts causing test disk exhaustion — purged
- [x] Test collection failure in test_task_recovery.py — fixed (try/except FileNotFoundError)
- [x] adversarial_review.py not wired to real DeliberationCouncil — fixed
- [x] Task state transitions not enforced — fixed with TaskStateMachine
```

---

### Verify

```bash
# No new Python files changed in this session — code must be identical before and after
git diff --name-only | grep -v "\.md$"
# Output must be empty — only .md files should have changed

# Confirm CLAUDE.md still reads as a coherent document (not fragmented by tags)
wc -l CLAUDE.md
cat CLAUDE.md | grep "\[Roadmap\]" | wc -l
# Should be a reasonable number — not zero (nothing tagged) and not 50+ (everything tagged)
```

---

### Commit message

```
docs: honest capability tagging in CLAUDE.md, README, add KNOWN_GAPS.md

- CLAUDE.md: tag every claim as [Implemented], [Partially implemented],
  [Implemented — not yet E2E proven], or [Roadmap — Phase N]
- README.md: add Current Status section; mark roadmap items explicitly
- KNOWN_GAPS.md: structured P0/P1/P2 gap tracking with resolved items
```

---
---

## Sequencing Summary

| Session | When | Duration | LLM Cost | What you need to do |
|---|---|---|---|---|
| **1 — Runway Clearer** | Days 1–2 | ~30 min | $0 | Paste prompt, review commit |
| **[Manual] Phase 5 Run** | Days 3–4 | ~3 hours | ~$5–8 | You personally run FORGE_TEST_PLAN.md Phase 0 through Phase 5 |
| **2 — Auth Layer** | Days 5–8 | ~2 hours | $0 | Paste prompt, personally verify 6 curl checks |
| **3 — Silent Fallbacks** | Days 9–10 | ~1.5 hours | $0 | Paste prompt, review commit |
| **[Manual] Prep Exam Sessions** | Days 11–12 | ~1 hour | $0 | Read these 5 prompts; adjust anything based on Phase 5 results |
| **4 — Schema + LLM Architect** | Exam Week 1-A | ~20 min to kick off | $0 | Paste prompt during study break |
| **5 — Task State Machine** | Exam Week 1-B | ~20 min to kick off | $0 | Paste prompt |
| **6 — Split Health** | Exam Week 1-C | ~20 min to kick off | $0 | Paste prompt |
| **7 — Deployment Proof** | Exam Week 2-D | ~30 min to kick off | ~$5–8 | Paste prompt; needs real API keys active |
| **8 — Docs Audit** | Exam Week 2-E | ~20 min to kick off | $0 | Paste prompt |

## What You Will Have After All Eight Sessions

- Clean test suite passing at ≥95% with zero collection errors
- Bearer token auth on all APIs, production startup guard
- Every silent fallback now logs warnings and reports `healthy=False`
- Task state transitions enforced — illegal transitions impossible
- Health split into liveness / readiness / recovery
- Component registry fully machine-readable — LLM architect on by default
- One real end-to-end deployment proven on live infrastructure
- Documentation that matches what's actually built

That is launch-ready in the honest sense: not feature-complete, but production-honest and ready for a first pilot conversation with a real firm.
