# General Employee Kernel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a certified Forge employee baseline with dual knowledge-work and business-process lanes, configured by workflow packs.

**Architecture:** Add a reusable kernel contract inside `employee_runtime/core`, add workflow-pack definitions under `employee_runtime/workflow_packs`, integrate baseline metadata into runtime task execution and metrics, then enforce a baseline evaluator suite in the factory pipeline. The first implementation should preserve existing `executive_assistant` and `legal_intake` behavior while adding baseline certification surfaces.

**Tech Stack:** Python 3.12, Pydantic, FastAPI, LangGraph runtime, existing Forge component library, pytest/httpx test stack.

---

## File Structure

- Create `employee_runtime/core/kernel.py`: task lane enum, task plan schema, classification/planning helpers, ROI event schema.
- Create `employee_runtime/workflow_packs/__init__.py`: exported pack loader API.
- Create `employee_runtime/workflow_packs/base.py`: workflow-pack Pydantic schemas.
- Create `employee_runtime/workflow_packs/registry.py`: built-in pack registry and selection helpers.
- Create `employee_runtime/workflow_packs/packs.py`: initial pack definitions.
- Modify `employee_runtime/core/api.py`: initialize packs, attach kernel metadata to task context/result, expose richer ROI metrics.
- Modify `employee_runtime/core/task_repository.py`: persist kernel metadata in `workflow_output` without schema changes.
- Create `factory/pipeline/evaluator/baseline_tests.py`: universal certification suite.
- Modify `factory/pipeline/evaluator/test_runner.py`: always run baseline suite before role-specific functional suite.
- Modify `factory/pipeline/builder/config_generator.py`: include selected workflow packs and kernel baseline manifest in runtime config.
- Test with `tests/runtime/test_general_employee_kernel.py`, `tests/runtime/test_workflow_packs.py`, `tests/factory/test_pipeline/test_baseline_evaluator.py`, and focused existing runtime tests.

---

### Task 1: Add Workflow Pack Schemas And Registry

**Files:**
- Create: `employee_runtime/workflow_packs/__init__.py`
- Create: `employee_runtime/workflow_packs/base.py`
- Create: `employee_runtime/workflow_packs/registry.py`
- Create: `employee_runtime/workflow_packs/packs.py`
- Test: `tests/runtime/test_workflow_packs.py`

- [ ] **Step 1: Write the failing workflow-pack tests**

Create `tests/runtime/test_workflow_packs.py`:

```python
from __future__ import annotations

from employee_runtime.workflow_packs import get_workflow_pack, list_workflow_packs, select_pack_ids


def test_builtin_workflow_packs_are_registered() -> None:
    packs = list_workflow_packs()
    pack_ids = {pack.pack_id for pack in packs}

    assert {
        "executive_assistant_pack",
        "operations_coordinator_pack",
        "accounting_ops_pack",
        "legal_intake_pack",
    }.issubset(pack_ids)


def test_workflow_pack_exposes_baseline_contract_fields() -> None:
    pack = get_workflow_pack("operations_coordinator_pack")

    assert pack.display_name == "Operations Coordinator"
    assert "business_process" in pack.supported_lanes
    assert pack.required_tools
    assert pack.output_templates["business_process"]
    assert pack.evaluation_cases
    assert pack.roi_metrics["default_minutes_saved"] > 0


def test_select_pack_ids_uses_role_and_required_tools() -> None:
    selected = select_pack_ids(
        role_title="AI Accountant",
        required_tools=["email", "calendar", "messaging"],
    )

    assert "accounting_ops_pack" in selected
    assert "executive_assistant_pack" in selected
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/runtime/test_workflow_packs.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'employee_runtime.workflow_packs'`.

- [ ] **Step 3: Implement workflow-pack schemas**

Create `employee_runtime/workflow_packs/base.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class WorkflowPackEvaluationCase(BaseModel):
    case_id: str
    input: str
    expected_lane: str
    required_terms: list[str] = Field(default_factory=list)


class WorkflowPack(BaseModel):
    pack_id: str
    display_name: str
    version: str = "1.0.0"
    description: str
    supported_lanes: list[str]
    classification_hints: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    optional_tools: list[str] = Field(default_factory=list)
    output_templates: dict[str, str] = Field(default_factory=dict)
    autonomy_overrides: dict[str, str] = Field(default_factory=dict)
    domain_vocabulary: list[str] = Field(default_factory=list)
    onboarding_questions: list[str] = Field(default_factory=list)
    evaluation_cases: list[WorkflowPackEvaluationCase] = Field(default_factory=list)
    roi_metrics: dict[str, float] = Field(default_factory=dict)
```

- [ ] **Step 4: Implement built-in packs and registry**

Create `employee_runtime/workflow_packs/packs.py`:

```python
from __future__ import annotations

from employee_runtime.workflow_packs.base import WorkflowPack, WorkflowPackEvaluationCase


BUILTIN_WORKFLOW_PACKS: tuple[WorkflowPack, ...] = (
    WorkflowPack(
        pack_id="executive_assistant_pack",
        display_name="Executive Assistant",
        description="Scheduling, inbox triage, follow-ups, meeting prep, and briefings.",
        supported_lanes=["knowledge_work", "business_process", "hybrid"],
        classification_hints=["schedule", "meeting", "follow up", "briefing", "inbox"],
        required_tools=["email_tool", "calendar_tool", "messaging_tool"],
        optional_tools=["crm_tool"],
        output_templates={
            "knowledge_work": "Executive brief with summary, decisions, and next actions.",
            "business_process": "Action log with calendar, message, CRM, and approval updates.",
            "hybrid": "Brief plus action log.",
        },
        autonomy_overrides={"external_send": "approval_required"},
        domain_vocabulary=["briefing", "calendar hold", "follow-up", "action item"],
        onboarding_questions=["Who is the supervisor?", "Which calendar and inbox should I monitor?"],
        evaluation_cases=[
            WorkflowPackEvaluationCase(
                case_id="ea_schedule_followup",
                input="Schedule a review with Sarah next week and draft the follow-up.",
                expected_lane="hybrid",
                required_terms=["schedule", "follow-up"],
            )
        ],
        roi_metrics={"default_minutes_saved": 30.0},
    ),
    WorkflowPack(
        pack_id="operations_coordinator_pack",
        display_name="Operations Coordinator",
        description="Task routing, checklist execution, system updates, and exception reporting.",
        supported_lanes=["business_process", "hybrid"],
        classification_hints=["checklist", "update record", "route", "status", "exception"],
        required_tools=["email_tool", "messaging_tool"],
        optional_tools=["calendar_tool", "crm_tool", "custom_api_tool"],
        output_templates={
            "business_process": "Operations action log with completed steps and exceptions.",
            "hybrid": "Operations summary plus action log.",
        },
        autonomy_overrides={"record_update": "autonomous", "external_send": "approval_required"},
        domain_vocabulary=["SLA", "handoff", "exception", "owner", "status"],
        onboarding_questions=["Which systems of record can I update?", "Who receives exception reports?"],
        evaluation_cases=[
            WorkflowPackEvaluationCase(
                case_id="ops_status_update",
                input="Update the onboarding checklist, flag missing documents, and notify the owner.",
                expected_lane="business_process",
                required_terms=["checklist", "missing documents", "owner"],
            )
        ],
        roi_metrics={"default_minutes_saved": 25.0},
    ),
    WorkflowPack(
        pack_id="accounting_ops_pack",
        display_name="Accounting Operations",
        description="AP follow-up, close checklist support, variance explanation, and reconciliation triage.",
        supported_lanes=["knowledge_work", "business_process", "hybrid"],
        classification_hints=["invoice", "AP", "AR", "close", "variance", "reconcile"],
        required_tools=["email_tool", "calendar_tool"],
        optional_tools=["file_storage_tool", "custom_api_tool"],
        output_templates={
            "knowledge_work": "Finance memo with assumptions, calculations, and review flags.",
            "business_process": "Accounting action log with invoices, owners, amounts, and exceptions.",
            "hybrid": "Finance memo plus action log.",
        },
        autonomy_overrides={"post_journal_entry": "approval_required", "file_tax_return": "forbidden"},
        domain_vocabulary=["invoice", "aging", "variance", "close checklist", "reconciliation"],
        onboarding_questions=["What chart of accounts and close calendar should I use?", "Who approves finance actions?"],
        evaluation_cases=[
            WorkflowPackEvaluationCase(
                case_id="accounting_ap_followup",
                input="Review AP aging and draft follow-up actions for overdue invoices.",
                expected_lane="hybrid",
                required_terms=["AP", "overdue", "follow-up"],
            )
        ],
        roi_metrics={"default_minutes_saved": 45.0},
    ),
    WorkflowPack(
        pack_id="legal_intake_pack",
        display_name="Legal Intake",
        description="Inquiry triage, conflict packet prep, deadline extraction, and attorney escalation.",
        supported_lanes=["knowledge_work", "business_process", "hybrid"],
        classification_hints=["intake", "conflict", "matter", "deadline", "attorney"],
        required_tools=["email_tool", "calendar_tool"],
        optional_tools=["file_storage_tool", "document_ingestion"],
        output_templates={
            "knowledge_work": "Intake brief with facts, risks, deadlines, and attorney questions.",
            "business_process": "Intake action log with conflict, document, calendar, and escalation steps.",
            "hybrid": "Intake brief plus action log.",
        },
        autonomy_overrides={"legal_advice": "forbidden", "case_acceptance": "approval_required"},
        domain_vocabulary=["matter", "conflict", "deadline", "retainer", "intake"],
        onboarding_questions=["Who reviews new matters?", "What conflict sources should I check?"],
        evaluation_cases=[
            WorkflowPackEvaluationCase(
                case_id="legal_intake_packet",
                input="Prepare an intake packet and flag conflict-check needs for this new inquiry.",
                expected_lane="hybrid",
                required_terms=["intake", "conflict"],
            )
        ],
        roi_metrics={"default_minutes_saved": 40.0},
    ),
)
```

Create `employee_runtime/workflow_packs/registry.py`:

```python
from __future__ import annotations

from employee_runtime.workflow_packs.base import WorkflowPack
from employee_runtime.workflow_packs.packs import BUILTIN_WORKFLOW_PACKS

_PACKS: dict[str, WorkflowPack] = {pack.pack_id: pack for pack in BUILTIN_WORKFLOW_PACKS}


def list_workflow_packs() -> list[WorkflowPack]:
    return list(_PACKS.values())


def get_workflow_pack(pack_id: str) -> WorkflowPack:
    try:
        return _PACKS[pack_id]
    except KeyError as exc:
        raise ValueError(f"Unknown workflow pack '{pack_id}'. Available: {sorted(_PACKS)}") from exc


def select_pack_ids(role_title: str, required_tools: list[str] | None = None) -> list[str]:
    lowered_role = role_title.lower()
    selected = ["executive_assistant_pack"]
    if "account" in lowered_role or "finance" in lowered_role:
        selected.append("accounting_ops_pack")
    if "legal" in lowered_role or "law" in lowered_role or "intake" in lowered_role:
        selected.append("legal_intake_pack")
    if "ops" in lowered_role or "operation" in lowered_role or "coordinator" in lowered_role:
        selected.append("operations_coordinator_pack")
    if required_tools and any(tool in {"custom_api", "crm", "crm_tool", "custom_api_tool"} for tool in required_tools):
        selected.append("operations_coordinator_pack")
    return sorted(set(selected), key=selected.index)
```

Create `employee_runtime/workflow_packs/__init__.py`:

```python
from employee_runtime.workflow_packs.base import WorkflowPack, WorkflowPackEvaluationCase
from employee_runtime.workflow_packs.registry import get_workflow_pack, list_workflow_packs, select_pack_ids

__all__ = [
    "WorkflowPack",
    "WorkflowPackEvaluationCase",
    "get_workflow_pack",
    "list_workflow_packs",
    "select_pack_ids",
]
```

- [ ] **Step 5: Run workflow-pack tests**

Run:

```bash
.venv/bin/pytest tests/runtime/test_workflow_packs.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add employee_runtime/workflow_packs tests/runtime/test_workflow_packs.py
git commit -m "feat: add workflow pack registry"
```

---

### Task 2: Add Kernel Classification, Planning, And ROI Contracts

**Files:**
- Create: `employee_runtime/core/kernel.py`
- Test: `tests/runtime/test_general_employee_kernel.py`

- [ ] **Step 1: Write failing kernel contract tests**

Create `tests/runtime/test_general_employee_kernel.py`:

```python
from __future__ import annotations

from employee_runtime.core.kernel import classify_task, create_task_plan, estimate_roi, task_plan_to_context
from employee_runtime.workflow_packs import get_workflow_pack


def test_classify_task_identifies_knowledge_work() -> None:
    result = classify_task("Prepare a concise investor update from these notes.", [])

    assert result.lane == "knowledge_work"
    assert result.confidence >= 0.7


def test_classify_task_identifies_business_process() -> None:
    result = classify_task("Update the CRM record, route approval, and notify the account owner.", [])

    assert result.lane == "business_process"
    assert result.confidence >= 0.7


def test_classify_task_identifies_hybrid_work() -> None:
    result = classify_task("Draft the client follow-up and schedule the review meeting.", [])

    assert result.lane == "hybrid"


def test_create_task_plan_uses_pack_template_and_approval_points() -> None:
    pack = get_workflow_pack("accounting_ops_pack")
    classification = classify_task("Review AP aging and draft follow-up for overdue invoices.", [pack])

    plan = create_task_plan(
        task_input="Review AP aging and draft follow-up for overdue invoices.",
        classification=classification,
        packs=[pack],
    )

    assert plan.lane == "hybrid"
    assert "Deliver professional output" in plan.steps
    assert "external_send" in plan.approval_points
    assert plan.output_template


def test_task_plan_to_context_is_serializable() -> None:
    pack = get_workflow_pack("operations_coordinator_pack")
    plan = create_task_plan(
        task_input="Update checklist and notify the owner.",
        classification=classify_task("Update checklist and notify the owner.", [pack]),
        packs=[pack],
    )

    context = task_plan_to_context(plan)

    assert context["kernel"]["task_lane"] in {"business_process", "hybrid"}
    assert context["kernel"]["plan"]["steps"]


def test_estimate_roi_uses_pack_minutes_saved() -> None:
    pack = get_workflow_pack("legal_intake_pack")

    roi = estimate_roi([pack], completed_tasks=2, escalations=1, rework_events=0)

    assert roi["estimated_minutes_saved"] == 80.0
    assert roi["completed_tasks"] == 2
    assert roi["escalations"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/runtime/test_general_employee_kernel.py -q
```

Expected: FAIL with `ImportError` for `employee_runtime.core.kernel`.

- [ ] **Step 3: Implement kernel contracts**

Create `employee_runtime/core/kernel.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field

from employee_runtime.workflow_packs.base import WorkflowPack


KNOWLEDGE_TERMS = {
    "prepare", "draft", "summarize", "analyze", "brief", "memo", "report",
    "research", "recommend", "compare", "explain", "investor", "client-ready",
}
PROCESS_TERMS = {
    "update", "route", "notify", "schedule", "create", "mark", "reconcile",
    "checklist", "crm", "calendar", "send", "approve", "owner", "record",
}
RISKY_ACTIONS = {"external_send", "post_journal_entry", "case_acceptance", "legal_advice", "file_tax_return"}


class TaskClassification(BaseModel):
    lane: str
    confidence: float
    matched_terms: list[str] = Field(default_factory=list)
    rationale: str


class KernelTaskPlan(BaseModel):
    lane: str
    steps: list[str]
    required_tools: list[str] = Field(default_factory=list)
    expected_deliverables: list[str] = Field(default_factory=list)
    approval_points: list[str] = Field(default_factory=list)
    output_template: str = ""
    completion_criteria: list[str] = Field(default_factory=list)
    pack_ids: list[str] = Field(default_factory=list)


def classify_task(task_input: str, packs: list[WorkflowPack]) -> TaskClassification:
    lowered = task_input.lower()
    knowledge_matches = sorted(term for term in KNOWLEDGE_TERMS if term in lowered)
    process_matches = sorted(term for term in PROCESS_TERMS if term in lowered)
    for pack in packs:
        for hint in pack.classification_hints:
            if hint.lower() in lowered:
                if "business_process" in pack.supported_lanes:
                    process_matches.append(hint)
                if "knowledge_work" in pack.supported_lanes:
                    knowledge_matches.append(hint)
    if knowledge_matches and process_matches:
        lane = "hybrid"
    elif process_matches:
        lane = "business_process"
    else:
        lane = "knowledge_work"
    confidence = 0.55 + min(0.4, 0.08 * (len(set(knowledge_matches + process_matches))))
    return TaskClassification(
        lane=lane,
        confidence=round(confidence, 2),
        matched_terms=sorted(set(knowledge_matches + process_matches)),
        rationale=f"Classified as {lane} from matched task and workflow-pack terms.",
    )


def create_task_plan(
    *,
    task_input: str,
    classification: TaskClassification,
    packs: list[WorkflowPack],
) -> KernelTaskPlan:
    lane = classification.lane
    steps = ["Understand requested outcome", "Gather available context"]
    if lane in {"knowledge_work", "hybrid"}:
        steps.extend(["Analyze inputs and assumptions", "Compose professional deliverable"])
    if lane in {"business_process", "hybrid"}:
        steps.extend(["Validate required fields", "Execute allowed system actions through ToolBroker"])
    steps.append("Deliver professional output")

    required_tools: list[str] = []
    approval_points = ["external_send"]
    output_template = ""
    for pack in packs:
        required_tools.extend(pack.required_tools)
        output_template = output_template or pack.output_templates.get(lane) or pack.output_templates.get("hybrid", "")
        approval_points.extend(action for action, mode in pack.autonomy_overrides.items() if mode != "autonomous")

    if classification.confidence < 0.7:
        approval_points.append("low_confidence_clarification")

    return KernelTaskPlan(
        lane=lane,
        steps=list(dict.fromkeys(steps)),
        required_tools=list(dict.fromkeys(required_tools)),
        expected_deliverables=["brief_card", "action_log" if lane in {"business_process", "hybrid"} else "written_deliverable"],
        approval_points=sorted(set(approval_points) & (RISKY_ACTIONS | {"low_confidence_clarification"})),
        output_template=output_template or "Professional task brief with summary, evidence, actions, and next steps.",
        completion_criteria=["output_created", "audit_recorded", "roi_recorded"],
        pack_ids=[pack.pack_id for pack in packs],
    )


def task_plan_to_context(plan: KernelTaskPlan) -> dict[str, object]:
    return {
        "kernel": {
            "task_lane": plan.lane,
            "plan": plan.model_dump(mode="json"),
        }
    }


def estimate_roi(
    packs: list[WorkflowPack],
    *,
    completed_tasks: int,
    escalations: int,
    rework_events: int,
) -> dict[str, float | int]:
    minutes_per_task = max([pack.roi_metrics.get("default_minutes_saved", 20.0) for pack in packs] or [20.0])
    penalty = (escalations * 5.0) + (rework_events * 15.0)
    return {
        "completed_tasks": completed_tasks,
        "escalations": escalations,
        "rework_events": rework_events,
        "estimated_minutes_saved": max(0.0, round((completed_tasks * minutes_per_task) - penalty, 2)),
    }
```

- [ ] **Step 4: Run kernel tests**

Run:

```bash
.venv/bin/pytest tests/runtime/test_general_employee_kernel.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add employee_runtime/core/kernel.py tests/runtime/test_general_employee_kernel.py
git commit -m "feat: add general employee kernel contracts"
```

---

### Task 3: Integrate Kernel Metadata Into Runtime Task Execution

**Files:**
- Modify: `employee_runtime/core/api.py`
- Test: `tests/runtime/test_general_employee_kernel.py`

- [ ] **Step 1: Add failing runtime integration test**

Append to `tests/runtime/test_general_employee_kernel.py`:

```python
import pytest
from httpx import ASGITransport, AsyncClient

from employee_runtime.core.api import create_employee_app


def _kernel_manifest() -> dict[str, object]:
    return {
        "manifest": {
            "employee_id": "kernel-avery",
            "org_id": "org-1",
            "employee_name": "Avery",
            "role_title": "AI Operations Employee",
            "employee_type": "executive_assistant",
            "workflow": "executive_assistant",
            "workflow_packs": ["executive_assistant_pack", "operations_coordinator_pack"],
            "tool_permissions": ["email_tool", "calendar_tool", "messaging_tool", "crm_tool"],
            "identity_layers": {
                "layer_1_core_identity": "You are a Forge AI Employee.",
                "layer_2_role_definition": "You are Avery, AI Operations Employee.",
                "layer_3_organizational_map": "Report to Operations Lead.",
                "layer_4_behavioral_rules": "Ask before high-risk external sends.",
                "layer_5_retrieved_context": "",
                "layer_6_self_awareness": "You can plan knowledge work and process work.",
            },
            "components": [
                {"id": "workflow_executor", "category": "work", "config": {}},
                {"id": "communication_manager", "category": "work", "config": {}},
                {"id": "scheduler_manager", "category": "work", "config": {}},
                {"id": "email_tool", "category": "tools", "config": {}},
                {"id": "calendar_tool", "category": "tools", "config": {}},
                {"id": "messaging_tool", "category": "tools", "config": {}},
                {"id": "crm_tool", "category": "tools", "config": {}},
                {"id": "operational_memory", "category": "data", "config": {}},
                {"id": "working_memory", "category": "data", "config": {}},
                {"id": "context_assembler", "category": "data", "config": {}},
                {"id": "org_context", "category": "data", "config": {}},
                {"id": "audit_system", "category": "quality", "config": {}},
                {"id": "explainability", "category": "quality", "config": {}},
                {"id": "autonomy_manager", "category": "quality", "config": {}},
                {"id": "input_protection", "category": "quality", "config": {}},
            ],
            "ui": {"app_badge": "Baseline", "capabilities": ["plan work", "execute workflows"]},
            "org_map": [],
        }
    }


@pytest.mark.anyio
async def test_runtime_persists_kernel_plan_and_roi_metadata() -> None:
    app = create_employee_app("kernel-avery", _kernel_manifest())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tasks",
            json={
                "input": "Draft the client update, update the CRM record, and notify the account owner.",
                "context": {},
                "conversation_id": "default",
            },
        )
        assert response.status_code == 200
        task_id = response.json()["task_id"]
        task = (await client.get(f"/api/v1/tasks/{task_id}")).json()
        metrics = (await client.get("/api/v1/metrics")).json()

    kernel = task["workflow_output"]["kernel"]
    assert kernel["task_lane"] == "hybrid"
    assert kernel["plan"]["required_tools"]
    assert metrics["roi"]["estimated_minutes_saved"] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/runtime/test_general_employee_kernel.py::test_runtime_persists_kernel_plan_and_roi_metadata -q
```

Expected: FAIL because `workflow_output.kernel` and `metrics.roi` are absent.

- [ ] **Step 3: Integrate kernel planning into `EmployeeRuntimeService.submit_task`**

In `employee_runtime/core/api.py`, import the kernel and pack loader near the existing imports:

```python
from employee_runtime.core.kernel import classify_task, create_task_plan, estimate_roi, task_plan_to_context
from employee_runtime.workflow_packs import get_workflow_pack
```

Add a helper method on `EmployeeRuntimeService`:

```python
    def _workflow_packs(self) -> list[Any]:
        pack_ids = self.config.get("workflow_packs", ["executive_assistant_pack"])
        packs = []
        for pack_id in pack_ids:
            packs.append(get_workflow_pack(str(pack_id)))
        return packs
```

Inside `submit_task`, before `self.engine.process_task(...)`, compute and merge kernel context:

```python
        packs = self._workflow_packs()
        classification = classify_task(request.input, packs)
        plan = create_task_plan(task_input=request.input, classification=classification, packs=packs)
        kernel_context = task_plan_to_context(plan)
        enriched_context = {**dict(request.context), **kernel_context}
```

Use `enriched_context` when calling `engine.process_task`:

```python
                metadata=enriched_context,
```

After `result` is returned and before persistence, merge kernel data into `workflow_output`:

```python
        workflow_output = dict(result.get("workflow_output", {}))
        workflow_output["kernel"] = {
            **kernel_context["kernel"],
            "classification": classification.model_dump(mode="json"),
        }
```

Then persist `workflow_output` instead of `dict(result.get("workflow_output", {}))`.

- [ ] **Step 4: Add ROI to metrics**

In `EmployeeRuntimeService.metrics`, compute task counts and correction count:

```python
        corrections = await self.list_corrections()
        packs = self._workflow_packs()
        roi = estimate_roi(
            packs,
            completed_tasks=len(completed),
            escalations=len([event for event in activity if event["event_type"] == "approval_requested"]),
            rework_events=len(corrections),
        )
```

Add `"roi": roi` to the returned metrics payload.

- [ ] **Step 5: Run runtime integration test**

Run:

```bash
.venv/bin/pytest tests/runtime/test_general_employee_kernel.py::test_runtime_persists_kernel_plan_and_roi_metadata -q
```

Expected: PASS.

- [ ] **Step 6: Run related runtime tests**

Run:

```bash
.venv/bin/pytest tests/runtime/test_employee_api.py tests/runtime/test_autonomous_daily_loop.py tests/runtime/test_general_employee_kernel.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add employee_runtime/core/api.py tests/runtime/test_general_employee_kernel.py
git commit -m "feat: attach kernel planning to employee tasks"
```

---

### Task 4: Add Baseline Certification Evaluator

**Files:**
- Create: `factory/pipeline/evaluator/baseline_tests.py`
- Modify: `factory/pipeline/evaluator/test_runner.py`
- Test: `tests/factory/test_pipeline/test_baseline_evaluator.py`

- [ ] **Step 1: Write failing evaluator tests**

Create `tests/factory/test_pipeline/test_baseline_evaluator.py`:

```python
from __future__ import annotations

import pytest

from factory.pipeline.evaluator.baseline_tests import run_baseline_tests


class FakeResponse:
    def __init__(self, status_code: int, payload: dict[str, object]) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict[str, object]:
        return self._payload


class FakeClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    async def __aenter__(self) -> "FakeClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, path: str, json: dict[str, object]) -> FakeResponse:
        self.requests.append({"path": path, "json": json})
        task_id = f"task-{len(self.requests)}"
        brief = {
            "title": "Baseline Result",
            "executive_summary": "Completed baseline task with evidence and action log.",
            "action_items": ["next step"],
        }
        return FakeResponse(200, {"task_id": task_id, "status": "completed", "brief": brief})

    async def get(self, path: str) -> FakeResponse:
        if path.endswith("/metrics"):
            return FakeResponse(200, {"roi": {"estimated_minutes_saved": 75.0}, "tasks_total": 3})
        if "/tasks/" in path:
            return FakeResponse(
                200,
                {
                    "workflow_output": {
                        "kernel": {
                            "task_lane": "hybrid",
                            "plan": {"steps": ["Understand requested outcome"]},
                        }
                    },
                    "result_card": {"executive_summary": "Done"},
                },
            )
        return FakeResponse(200, {})


@pytest.mark.anyio
async def test_baseline_tests_require_kernel_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("factory.pipeline.evaluator.baseline_tests.httpx.AsyncClient", lambda **kwargs: FakeClient())

    result = await run_baseline_tests("http://test", auth_headers={"Authorization": "Bearer token"})

    assert result["passed"] is True
    assert result["tests"] >= 6
    assert not result["failures"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/factory/test_pipeline/test_baseline_evaluator.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `factory.pipeline.evaluator.baseline_tests`.

- [ ] **Step 3: Implement baseline evaluator suite**

Create `factory/pipeline/evaluator/baseline_tests.py`:

```python
from __future__ import annotations

from typing import Any

import httpx

BASELINE_CASES = [
    {
        "id": "knowledge_work",
        "input": "Prepare a concise client-ready update with assumptions and next steps.",
        "expected_lane": "knowledge_work",
    },
    {
        "id": "business_process",
        "input": "Update the checklist, route approval, and notify the account owner.",
        "expected_lane": "business_process",
    },
    {
        "id": "hybrid",
        "input": "Draft the client follow-up, schedule the review meeting, and update the CRM record.",
        "expected_lane": "hybrid",
    },
]


async def run_baseline_tests(base_url: str, *, auth_headers: dict[str, str] | None = None) -> dict[str, Any]:
    failures: list[str] = []
    tests_run = 0
    async with httpx.AsyncClient(base_url=base_url, timeout=120, headers=auth_headers) as client:
        for case in BASELINE_CASES:
            response = await client.post(
                "/api/v1/tasks",
                json={"input": case["input"], "context": {"evaluation_fixture": case["id"]}, "conversation_id": "baseline-eval"},
            )
            tests_run += 1
            if response.status_code != 200:
                failures.append(f"{case['id']}: task returned HTTP {response.status_code}")
                continue
            task_id = str(response.json().get("task_id", ""))
            task_response = await client.get(f"/api/v1/tasks/{task_id}")
            tests_run += 1
            if task_response.status_code != 200:
                failures.append(f"{case['id']}: task status returned HTTP {task_response.status_code}")
                continue
            task = task_response.json()
            kernel = task.get("workflow_output", {}).get("kernel", {})
            lane = str(kernel.get("task_lane", ""))
            if lane != case["expected_lane"]:
                failures.append(f"{case['id']}: expected lane {case['expected_lane']} got {lane}")
            if not kernel.get("plan", {}).get("steps"):
                failures.append(f"{case['id']}: missing kernel plan steps")
            if not task.get("result_card") and not response.json().get("brief"):
                failures.append(f"{case['id']}: missing professional output card")

        metrics_response = await client.get("/api/v1/metrics")
        tests_run += 1
        if metrics_response.status_code != 200:
            failures.append(f"metrics: returned HTTP {metrics_response.status_code}")
        else:
            metrics = metrics_response.json()
            if metrics.get("roi", {}).get("estimated_minutes_saved", 0) <= 0:
                failures.append("metrics: missing positive ROI estimate")

    return {"passed": not failures, "tests": tests_run, "failures": failures, "cases": BASELINE_CASES}
```

- [ ] **Step 4: Wire baseline suite into evaluator**

In `factory/pipeline/evaluator/test_runner.py`, import the suite:

```python
from factory.pipeline.evaluator.baseline_tests import run_baseline_tests
```

Add it to the `suites` dict before security:

```python
        suites = {
            "baseline": await _run_suite(run_baseline_tests, base_url, auth_headers),
            "security": await _run_suite(run_security_tests, base_url, auth_headers),
            "behavioral": await _run_suite(run_behavioral_tests, base_url, auth_headers),
            "hallucination": await _run_suite(run_hallucination_tests, base_url, auth_headers),
        }
```

- [ ] **Step 5: Run evaluator tests**

Run:

```bash
.venv/bin/pytest tests/factory/test_pipeline/test_baseline_evaluator.py tests/factory/test_pipeline/test_evaluator.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add factory/pipeline/evaluator/baseline_tests.py factory/pipeline/evaluator/test_runner.py tests/factory/test_pipeline/test_baseline_evaluator.py
git commit -m "feat: require baseline employee certification"
```

---

### Task 5: Include Kernel Manifest And Workflow Packs In Generated Config

**Files:**
- Modify: `factory/pipeline/builder/config_generator.py`
- Test: `tests/factory/test_pipeline/test_assembler.py`

- [ ] **Step 1: Add failing config assertion**

In `tests/factory/test_pipeline/test_assembler.py`, extend the existing config/manifest assertion for assembled builds with:

```python
    config = json.loads(Path(build.metadata["config_path"]).read_text())
    manifest = config["manifest"]
    assert manifest["kernel_baseline"]["version"] == "1.0.0"
    assert manifest["kernel_baseline"]["required_lanes"] == ["knowledge_work", "business_process", "hybrid"]
    assert manifest["workflow_packs"]
```

- [ ] **Step 2: Run assembler test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/factory/test_pipeline/test_assembler.py -q
```

Expected: FAIL because `kernel_baseline` or `workflow_packs` is absent.

- [ ] **Step 3: Add config generation logic**

In `factory/pipeline/builder/config_generator.py`, import pack selection:

```python
from employee_runtime.workflow_packs import select_pack_ids
```

When building the manifest/config dictionary, compute:

```python
    workflow_packs = select_pack_ids(
        requirements.role_title or requirements.name,
        list(requirements.required_tools),
    )
    kernel_baseline = {
        "version": "1.0.0",
        "required_lanes": ["knowledge_work", "business_process", "hybrid"],
        "certification_required": True,
    }
```

Add both values to the runtime config and manifest:

```python
        "workflow_packs": workflow_packs,
        "kernel_baseline": kernel_baseline,
```

- [ ] **Step 4: Run assembler and runtime tests**

Run:

```bash
.venv/bin/pytest tests/factory/test_pipeline/test_assembler.py tests/runtime/test_general_employee_kernel.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factory/pipeline/builder/config_generator.py tests/factory/test_pipeline/test_assembler.py
git commit -m "feat: stamp kernel baseline into employee configs"
```

---

### Task 6: Verification Gate

**Files:**
- No new files.

- [ ] **Step 1: Run focused Python regression**

Run:

```bash
.venv/bin/pytest tests/runtime/test_workflow_packs.py tests/runtime/test_general_employee_kernel.py tests/runtime/test_employee_api.py tests/runtime/test_autonomous_daily_loop.py tests/factory/test_pipeline/test_baseline_evaluator.py tests/factory/test_pipeline/test_assembler.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full Python suite when local time allows**

Run:

```bash
.venv/bin/pytest -q
```

Expected: PASS or a clearly documented pre-existing/environment-gated failure.

- [ ] **Step 3: Run server-export preflight**

Run:

```bash
.venv/bin/python scripts/prove_server_export.py --mode preflight
```

Expected: JSON output with `"blockers": []`, or explicit environment blockers that are not introduced by this plan.

- [ ] **Step 4: Run employee app build if runtime API shape changed**

Run:

```bash
cd portal/employee_app && npm run build
```

Expected: PASS.

---

## Self-Review

Spec coverage:

- Kernel dual lanes are implemented by `TaskClassification`, `KernelTaskPlan`, and evaluator baseline cases.
- Workflow packs are implemented by the pack schema, registry, and initial built-in packs.
- Runtime integration is implemented in `EmployeeRuntimeService.submit_task` and `metrics`.
- Certification is implemented in `factory/pipeline/evaluator/baseline_tests.py`.
- Generated config stamping is implemented in `factory/pipeline/builder/config_generator.py`.

Open-item scan:

- This plan contains no open-ended implementation instructions, missing commands, or unspecified test steps.

Type consistency:

- Pack ids use `*_pack`.
- Lane values use `knowledge_work`, `business_process`, and `hybrid`.
- Runtime metadata is stored under `workflow_output["kernel"]`.
- ROI metrics are returned under `metrics()["roi"]`.
