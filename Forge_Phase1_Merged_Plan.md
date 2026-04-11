# FORGE PHASE 1 — MERGED BUILD PLAN
## Legal Intake Employee — Vertical Slice

> This document is the execution spec for Phase 1. It merges the architectural
> decisions from the Codex-generated implementation plan with the detailed
> implementation specs (prompts, schemas, test cases, UI designs) developed in
> planning. Feed this to Codex as the source of truth for each sprint.

---

## ARCHITECTURAL DECISIONS (from Codex analysis)

These override earlier build plan assumptions wherever they conflict:

1. **Tenancy:** `ClientOrg` and `org_id` are canonical. Use `org_id` everywhere in Phase 1. Do not introduce a separate `clients` table or `tenant_id` abstraction.

2. **Schema evolution:** Add a NEW Alembic migration for runtime tables (`operational_memories`, `conversations`, `messages`, and `audit_events` evolution). Do NOT rewrite the existing committed migration.

3. **Component instantiation:** Add a registry helper that instantiates and initializes selected components from config in one pass. Workflow nodes receive pre-initialized components via dependency injection — they do not construct components ad hoc.

4. **Settings persistence:** Store employee settings in `operational_memory` under preference keys (e.g., `pref:quiet_hours`, `pref:supervisor_email`). No separate settings table.

5. **Activity + metrics:** Derive from `audit_events` and `messages` tables via queries. No separate activity or metrics tables.

6. **Approval state:** Represent as message metadata in the `messages` table plus audit events. An approval is a message of type `approval_request` with metadata tracking the decision state. No separate approvals table.

7. **Email:** Mock implementation in Phase 1. All email actions route through `ToolBroker`. No direct IMAP/SMTP.

8. **Streaming:** LLM providers must support token-level streaming. Streaming flows end-to-end: LLM → engine → API → WebSocket → frontend.

9. **Scope:** Phase 1 delivers the legal intake employee vertical slice and employee app as a hosted web app. No factory automation, no Electron packaging, no Forge Pro catalog.

10. **Class name cleanup:** Fix mangled stub names (`UtextUprocessor` → `TextProcessor`, `UconfidenceUscorer` → `ConfidenceScorer`, etc.) as each stub is replaced.

---

## PHASE 1 SPRINT MAP

| Sprint | Focus | Duration |
|--------|-------|----------|
| 1 | Foundation reconciliation — DB migration, LLM streaming, registry helper | 3–5 days |
| 2 | Core work capabilities — text_processor, document_analyzer | 3–5 days |
| 3 | Memory, communication, quality — operational_memory, working_memory, context_assembler, org_context, confidence_scorer, audit_system, input_protection, mock email | 5–7 days |
| 4 | Legal intake workflow — LangGraph pipeline, draft_generator, verification_layer, engine update | 4–6 days |
| 5 | Employee app — Next.js frontend, expanded API, WebSocket streaming | 7–10 days |
| 6 | Polish + demo — error handling, morning briefing, metrics, demo suite | 5–7 days |

---

## SPRINT 1: FOUNDATION RECONCILIATION

### 1.1 Runtime Database Tables

Add a new Alembic migration that creates these tables alongside the existing schema:

```sql
CREATE TABLE operational_memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES client_orgs(id),
    employee_id VARCHAR NOT NULL,
    key VARCHAR NOT NULL,
    value JSONB NOT NULL,
    category VARCHAR NOT NULL DEFAULT 'general',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(org_id, employee_id, key)
);
CREATE INDEX idx_opmem_lookup ON operational_memories(org_id, employee_id, key);
CREATE INDEX idx_opmem_category ON operational_memories(org_id, employee_id, category);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES client_orgs(id),
    employee_id VARCHAR NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id),
    role VARCHAR NOT NULL,              -- user | assistant | system
    content TEXT NOT NULL,
    message_type VARCHAR NOT NULL DEFAULT 'text',  -- text | brief_card | approval_request | status_update | file
    metadata JSONB DEFAULT '{}',        -- brief data, approval state, file refs
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_messages_conv ON messages(conversation_id, created_at);

-- Evolve audit_events to support employee runtime tracing
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS employee_id VARCHAR;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS event_type VARCHAR;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS details JSONB DEFAULT '{}';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS prev_hash VARCHAR DEFAULT '';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS hash VARCHAR DEFAULT '';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS trace_id VARCHAR;
```

Implement as SQLAlchemy ORM models in `factory/models/orm.py` — extend the existing file, do not replace it.

### 1.2 Database Session Path

Update `factory/database.py`:
- Ensure `get_db_session()` returns an `AsyncSession` usable by both factory API code and employee runtime code in Phase 1
- Add `auto_init_db` support: when `AUTO_INIT_DB=true`, call `Base.metadata.create_all()` on startup (dev convenience)
- Ensure the engine uses `create_async_engine` with `asyncpg`

### 1.3 LLM Provider Streaming

Update `component_library/models/anthropic_provider.py`:
- Keep existing `initialize()` and `health_check()`
- Add `complete(system_prompt, user_message, **kwargs) -> str` — unstructured completion
- Add `complete_structured(system_prompt, user_message, output_model, **kwargs) -> BaseModel` — via Instructor
- Add `stream(system_prompt, user_message, **kwargs) -> AsyncGenerator[str, None]` — yields tokens for real-time streaming to the app
- Fix class to use litellm async calls properly

Update `component_library/models/litellm_router.py`:
- Add `TaskType` enum: PRIMARY, FALLBACK, REASONING, SAFETY, FAST, EMBEDDING
- Route to the correct model from `FactorySettings` based on `TaskType`
- Add `complete()`, `complete_structured()`, and `stream()` that delegate to the selected model
- Add cost tracking: log model, input_tokens, output_tokens, estimated_cost via structlog
- Add fallback: if primary model fails, retry with fallback model

### 1.4 Registry Helper

Create `component_library/component_factory.py` (new):

```python
async def create_components(
    component_ids: list[str],
    config: dict[str, dict],
) -> dict[str, BaseComponent]:
    """Instantiate and initialize a set of components from config.

    Args:
        component_ids: List of component IDs to create (e.g., ["text_processor", "confidence_scorer"])
        config: Dict mapping component_id -> config dict for that component

    Returns:
        Dict mapping component_id -> initialized component instance
    """
    from component_library.registry import get_component

    components = {}
    for cid in component_ids:
        cls = get_component(cid)
        instance = cls()
        await instance.initialize(config.get(cid, {}))
        components[cid] = instance
    return components
```

This is used by the engine to get all components ready before running the workflow.

### 1.5 Sprint 1 Tests

- Migration: tables exist, upgrade/downgrade succeeds
- LLM: `complete()` returns text, `complete_structured()` returns Pydantic model, `stream()` yields tokens
- Router: routes PRIMARY to the right model, falls back on failure
- Registry helper: creates and initializes multiple components from config

---

## SPRINT 2: CORE WORK CAPABILITIES

### 2.1 Category Subclass Interfaces

Add to `component_library/interfaces.py`:

```python
class WorkCapability(BaseComponent):
    """Base for work capability components (Category 2)."""
    category = "work"

    @abstractmethod
    async def execute(self, input_data: BaseModel) -> BaseModel:
        """Execute the work capability with typed input/output."""

class ToolIntegration(BaseComponent):
    """Base for tool integration components (Category 3)."""
    category = "tools"

    @abstractmethod
    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool action."""

class DataSource(BaseComponent):
    """Base for data source components (Category 4)."""
    category = "data"

    @abstractmethod
    async def query(self, query: str, **kwargs) -> Any:
        """Query the data source."""

class QualityModule(BaseComponent):
    """Base for quality/governance components (Category 5)."""
    category = "quality"

    @abstractmethod
    async def evaluate(self, input_data: Any) -> BaseModel:
        """Evaluate and return assessment."""
```

### 2.2 Legal Intake Schemas

Create `component_library/work/schemas.py`:

```python
class LegalIntakeExtraction(BaseModel):
    """Structured extraction from a legal intake email."""
    client_name: str = ""
    client_email: str = ""
    client_phone: str = ""
    matter_type: str = ""
    date_of_incident: str = ""
    opposing_party: str = ""
    key_facts: list[str] = Field(default_factory=list)
    urgency: str = "normal"  # low | normal | high | urgent
    potential_conflicts: list[str] = Field(default_factory=list)
    estimated_value: str = ""
    referral_source: str = ""
    raw_summary: str = ""
    extraction_confidence: float = 0.0

class DocumentAnalyzerOutput(BaseModel):
    summary: str
    key_findings: list[str]
    risk_flags: list[str]
    recommended_actions: list[str]
    qualification_decision: str  # qualified | not_qualified | needs_review
    qualification_reasoning: str
    confidence: float

class IntakeBrief(BaseModel):
    brief_id: str = Field(default_factory=lambda: str(uuid4()))
    client_info: LegalIntakeExtraction
    analysis: DocumentAnalyzerOutput
    confidence_score: float
    recommended_attorney: str = ""
    recommended_practice_area: str = ""
    next_steps: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ConfidenceReport(BaseModel):
    overall_score: float
    llm_self_assessment: float
    structural_score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    flags: list[str] = Field(default_factory=list)
    recommendation: str  # proceed | review | escalate

class InputProtectionResult(BaseModel):
    is_safe: bool
    risk_score: float
    flags: list[str] = Field(default_factory=list)
    sanitized_input: str
```

### 2.3 text_processor Implementation

Replace `component_library/work/text_processor.py`. Rename class `UtextUprocessor` → `TextProcessor`.

**System prompt for legal intake extraction:**

```
You are a legal intake processing specialist at a law firm. Your job is to extract
structured information from prospective client inquiry emails.

Extract the following fields. If a field is not mentioned in the email, leave it as
an empty string. Do NOT infer or fabricate information not explicitly stated.

Fields to extract:
- client_name: Full name of the prospective client
- client_email: Their email address
- client_phone: Their phone number
- matter_type: Type of legal matter (e.g., "personal injury", "employment discrimination",
  "commercial dispute", "family law", "real estate", "criminal defense")
- date_of_incident: When the relevant event occurred
- opposing_party: The other party involved (person, company, or entity)
- key_facts: List of the most important factual statements from the email (3-10 items)
- urgency: "low" (no time pressure), "normal" (standard), "high" (approaching deadline),
  "urgent" (immediate action needed, e.g., statute of limitations within 30 days)
- potential_conflicts: Names of any parties that should be checked for conflicts of interest
  (include the opposing party and any other named individuals or companies)
- estimated_value: Any mention of dollar amounts, damages, or financial impact
- referral_source: How they found the firm (if mentioned)
- raw_summary: A 2-3 sentence summary of the inquiry in your own words

Assign extraction_confidence between 0.0 and 1.0:
- 0.9-1.0: All critical fields (name, matter_type, key_facts) clearly present
- 0.7-0.89: Most fields present but some ambiguity
- 0.5-0.69: Significant gaps or unclear information
- Below 0.5: Very incomplete or confusing inquiry
```

Uses `litellm_router.complete_structured(TaskType.PRIMARY, system_prompt, email_text, LegalIntakeExtraction)`.

### 2.4 document_analyzer Implementation

Replace `component_library/work/document_analyzer.py`. Rename `UdocumentUanalyzer` → `DocumentAnalyzer`.

**System prompt for legal intake analysis:**

```
You are a senior legal intake analyst at a law firm. Given extracted client intake
data, produce a qualification assessment.

Evaluate:
1. Does this matter fall within the firm's practice areas? (provided in context)
2. Are there sufficient facts to evaluate the case?
3. Are there any red flags (potential fraud, statute of limitations issues,
   jurisdictional problems, unrealistic expectations)?
4. Is the potential value sufficient to justify taking the case?

Produce:
- summary: 2-3 sentence assessment
- key_findings: Important observations (3-5 items)
- risk_flags: Any concerns the attorney should know about
- recommended_actions: What should happen next (2-4 items)
- qualification_decision: "qualified" (take it), "not_qualified" (decline),
  or "needs_review" (attorney judgment required)
- qualification_reasoning: 2-3 sentences explaining your decision
- confidence: 0.0-1.0 in your assessment
```

### 2.5 Sample Test Emails

Create `tests/fixtures/sample_emails.py` with 5 emails:

**CLEAR_QUALIFIED:**
```
Subject: Car Accident - Need Legal Help

Dear Attorney,

My name is Sarah Johnson and I was involved in a car accident on February 15, 2026
at the intersection of Main St and Broadway in Springfield. The other driver, James
Miller, ran a red light and T-boned my vehicle. I was taken to Springfield General
Hospital where I was treated for a broken collarbone and whiplash.

I've been unable to work for the past 6 weeks. My medical bills are currently at
$45,000 and climbing. My car was totaled — it was a 2022 Honda Civic worth about $28,000.

I found your firm through a Google search. My phone number is (555) 123-4567 and
my email is sarah.johnson@email.com.

I'd like to schedule a consultation as soon as possible.

Thank you,
Sarah Johnson
```

Expected: `client_name="Sarah Johnson"`, `matter_type` contains "personal injury" or "car accident" or "auto accident", `urgency="normal"` or `"high"`, `extraction_confidence >= 0.8`, `qualification_decision="qualified"`

**CLEAR_UNQUALIFIED:**
```
Subject: Question about my parking ticket

Hi, I got a parking ticket last week for $75 and I think it's unfair because the
sign was blocked by a tree. Can you help me fight it? My name is Tom Davis, email
tom.davis@email.com.
```

Expected: `qualification_decision="not_qualified"`, low estimated_value, matter outside typical practice areas

**AMBIGUOUS:**
```
Subject: Legal matter

Hello, I have a situation at work that I think might be illegal. I don't want to
get into details over email but it involves my boss and some questionable practices.
Can someone call me? Thanks. - Mike
```

Expected: `extraction_confidence < 0.7`, many fields empty, `qualification_decision="needs_review"`, risk_flags include something about insufficient information

**POTENTIAL_CONFLICT:**
```
Subject: Breach of Contract — Anderson Manufacturing

Dear Counsel,

I'm reaching out regarding a breach of contract dispute with Anderson Manufacturing
LLC. I am the CEO of Pacific Supply Co. Anderson has failed to deliver $2.3 million
worth of industrial equipment per our agreement dated June 2025. We've attempted to
resolve this directly but they are now refusing to communicate.

Contact: Robert Chen, robert@pacificsupply.com, (555) 987-6543

We need to move quickly as the contract has a 12-month dispute resolution clause
that expires in August 2026.

Robert Chen
CEO, Pacific Supply Co.
```

Expected: `potential_conflicts` includes "Anderson Manufacturing", `urgency="high"`, `estimated_value` references "$2.3 million"

**URGENT:**
```
Subject: URGENT — Statute of Limitations Expiring

I was injured at my workplace 2 years and 11 months ago. I just learned that the
statute of limitations for personal injury in our state is 3 years. That means I
only have about 30 days to file. Please contact me IMMEDIATELY.

Maria Garcia, (555) 222-3333, maria.garcia@email.com
Injury: Chemical burn at Westfield Chemical plant on May 14, 2023
```

Expected: `urgency="urgent"`, `extraction_confidence >= 0.7`, `risk_flags` mentions statute of limitations, `recommended_actions` includes immediate action

### 2.6 Sprint 2 Tests

- `tests/components/work/test_text_processor.py` — all 5 emails through extraction, verify key fields
- `tests/components/work/test_document_analyzer.py` — extraction output through analysis, verify qualification decisions
- `tests/components/work/test_schemas.py` — Pydantic model validation, edge cases
- Gate LLM tests behind API key presence — skip if no key configured

---

## SPRINT 3: MEMORY, COMMUNICATION, AND QUALITY

### 3.1 operational_memory

Replace stub. Rename `UoperationalUmemory` → `OperationalMemory`. Inherits from `DataSource`.

- Postgres-backed using `operational_memories` table
- Methods: `store(key, value, category)`, `retrieve(key)`, `search(query, category, limit)`, `list_by_category(category)`, `delete(key)`
- All operations scoped by `org_id` + `employee_id`
- Upsert on store (ON CONFLICT UPDATE)
- Search uses `ILIKE` on key + text casting of JSONB value

### 3.2 working_memory

Replace stub. Rename `UworkingUmemory` → `WorkingMemory`. Inherits from `DataSource`.

- Redis-backed with async client
- Keys: `wm:{org_id}:{employee_id}:{task_id}:{key}`
- Methods: `set_context(task_id, key, value)`, `get_context(task_id, key)`, `get_all(task_id)`, `clear_task(task_id)`
- 24-hour TTL default (configurable)
- Values serialized as JSON

### 3.3 context_assembler

Replace stub. Rename `UcontextUassembler` → `ContextAssembler`. Inherits from `DataSource`.

Builds LLM context from all memory layers within a token budget:

```
Token allocation (8000 total budget):
├── System identity: ~800 tokens (role, rules, firm context)
├── Operational memory: ~1000 tokens (relevant known facts)
├── Conversation history: ~2000 tokens (recent messages)
├── Task input: variable
└── Reserved for response: ~2000 tokens
```

Method: `assemble(task_input, employee_id, org_id, conversation_id, token_budget) -> str`

Retrieves relevant operational memories by keyword-matching task input. Retrieves last N messages from conversation history. Assembles into structured context. Uses word_count * 1.3 as token estimate. Truncates oldest conversation messages first if over budget.

### 3.4 org_context

Replace stub. Rename `UorgUcontext` → `OrgContext`. Inherits from `DataSource`.

```python
class Person(BaseModel):
    name: str
    role: str
    email: str
    communication_preference: str = "email"
    relationship: str = "colleague"  # supervisor | colleague | client | vendor

class OrgContext(DataSource):
    # Initialized from config with people list, escalation chain, firm info
    # Methods: get_supervisor(), get_escalation_chain(), get_person(name), get_firm_info()
    # query() method for natural language lookups
```

### 3.5 confidence_scorer

Replace stub. Rename `UconfidenceUscorer` → `ConfidenceScorer`. Inherits from `QualityModule`.

Two modes:
- **LLM self-assessment:** Ask the model to rate confidence on a specific output
- **Structural checks:** Programmatic — field completeness, format validity (dates, phones, emails), consistency

Returns `ConfidenceReport` with `overall_score`, `llm_self_assessment`, `structural_score`, `dimension_scores`, `flags`, `recommendation` (proceed | review | escalate).

### 3.6 audit_system

Replace stub. Rename `UauditUsystem` → `AuditSystem`. Inherits from `QualityModule`.

- Append-only Postgres logging using `audit_events` table
- SHA-256 hash-chaining: `hash = SHA256(event_type | json(details) | timestamp_iso | prev_hash)`
- Methods: `log_event(employee_id, org_id, event_type, details) -> AuditEvent`, `get_trail(employee_id, since, event_type)`, `verify_chain(employee_id) -> ChainVerification`
- Event types: `task_created`, `task_started`, `task_completed`, `task_failed`, `llm_called`, `tool_invoked`, `output_produced`, `approval_requested`, `approval_decided`, `memory_stored`, `error_occurred`
- NEVER update or delete audit records

### 3.7 input_protection

Replace stub. Rename `UinputUprotection` → `InputProtection`. Inherits from `QualityModule`.

- Regex pattern matching for common prompt injection attempts
- Returns `InputProtectionResult` with `is_safe`, `risk_score`, `flags`, `sanitized_input`
- Patterns: "ignore previous instructions", "you are now", "disregard prior", "new instructions:", "system:", XML-style system tags

### 3.8 email_tool (Mock)

Replace stub. Rename `UemailUtool` → `EmailTool`. Inherits from `ToolIntegration`.

Mock implementation for Phase 1:
- `invoke("send", {to, subject, body})` → logs the email and stores it in a list
- `invoke("check_inbox", {criteria})` → returns from a pre-loaded fixture list
- `invoke("mark_read", {message_id})` → marks in the fixture list
- All actions route through `ToolBroker`
- Real IMAP/SMTP deferred to post-Phase 1

### 3.9 Sprint 3 Tests

- operational_memory: store, retrieve, search, category filter, upsert on duplicate key
- working_memory: set, get, clear, verify TTL expiry
- context_assembler: verify context within token budget, relevant facts included, truncation works
- org_context: supervisor lookup, escalation chain, person search
- confidence_scorer: both modes produce valid ConfidenceReport, structural checks catch missing fields
- audit_system: events logged, hash chain valid, verify_chain passes, tampering detected (modify one event → chain breaks)
- input_protection: catches injection patterns, passes clean input
- email_tool: mock send/receive/mark_read through ToolBroker

---

## SPRINT 4: LEGAL INTAKE WORKFLOW

### 4.1 EmployeeState as TypedDict

Replace `employee_runtime/core/state.py`:

```python
from typing import TypedDict

class EmployeeState(TypedDict, total=False):
    # Core
    task_id: str
    employee_id: str
    org_id: str

    # Input
    raw_input: str
    input_type: str        # email | form | api | transcript
    input_metadata: dict

    # Processing pipeline
    sanitization_result: dict    # InputProtectionResult
    extracted_data: dict         # LegalIntakeExtraction
    analysis: dict               # DocumentAnalyzerOutput
    confidence_report: dict      # ConfidenceReport
    verification_result: dict

    # Decision
    qualification_decision: str  # qualified | not_qualified | needs_review | escalated
    qualification_reasoning: str

    # Output
    brief: dict                  # IntakeBrief
    delivery_method: str
    delivery_status: str

    # Control
    errors: list
    audit_event_ids: list
    requires_human_approval: bool
    escalation_reason: str
    started_at: str
    completed_at: str
```

### 4.2 LangGraph Workflow

Create `employee_runtime/workflows/legal_intake.py`:

```
Graph: START → sanitize_input → extract_information → analyze_intake
       → score_confidence → route_by_confidence
           ├── [>= 0.85] → generate_brief → deliver
           ├── [0.4 – 0.85) → flag_for_review → generate_brief → deliver
           └── [< 0.4] → escalate → deliver
       → log_completion → END
```

Each node:
1. Receives `EmployeeState`
2. Gets its component from the injected component map
3. Calls the component
4. Logs to audit_system
5. Updates and returns state

`route_by_confidence` is a conditional edge function:
```python
def route_by_confidence(state: EmployeeState) -> str:
    score = state["confidence_report"]["overall_score"]
    if score >= 0.85:
        return "generate_brief"
    elif score >= 0.4:
        return "flag_for_review"
    else:
        return "escalate"
```

### 4.3 draft_generator

Replace stub. Rename `UdraftUgenerator` → `DraftGenerator`. Inherits from `WorkCapability`.

**System prompt:**
```
You are a senior legal intake coordinator. Given the following extracted client
information and qualification analysis, produce a concise intake brief for the
supervising attorney.

Structure:
1. One-paragraph executive summary
2. Qualification recommendation with reasoning
3. Recommended next steps (2-4 concrete actions)
4. Any flags or concerns the attorney should be aware of

Be clear about what is known, what is uncertain, and what requires the attorney's
judgment. Use professional but direct language.
```

Takes `LegalIntakeExtraction` + `DocumentAnalyzerOutput` + `ConfidenceReport` → produces `IntakeBrief`.

### 4.4 verification_layer

Replace stub. Rename `UverificationUlayer` → `VerificationLayer`. Inherits from `QualityModule`.

Programmatic checks on the IntakeBrief:
- All required fields populated (client_name, matter_type, qualification_decision)
- Date formats valid
- Phone/email format plausible
- Qualification decision consistent with confidence score
- No obvious contradictions (e.g., "qualified" with confidence < 0.3)

### 4.5 Engine Update

Update `employee_runtime/core/engine.py`:

```python
class EmployeeEngine:
    def __init__(self, workflow_name: str, components: dict[str, BaseComponent], config: dict):
        self._components = components
        self._config = config
        self._graph = self._build_graph(workflow_name)
        self._app = self._graph.compile()

    def _build_graph(self, name: str) -> StateGraph:
        if name == "legal_intake":
            from employee_runtime.workflows.legal_intake import build_graph
            return build_graph(self._components)
        raise ValueError(f"Unknown workflow: {name}")

    async def process_task(self, task_input: str, input_type: str = "email",
                           metadata: dict = None) -> EmployeeState:
        initial_state: EmployeeState = {
            "task_id": str(uuid4()),
            "employee_id": self._config["employee_id"],
            "org_id": self._config["org_id"],
            "raw_input": task_input,
            "input_type": input_type,
            "input_metadata": metadata or {},
            "errors": [],
            "audit_event_ids": [],
            "requires_human_approval": False,
            "escalation_reason": "",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": "",
            # ... defaults for all other fields
        }
        result = await self._app.ainvoke(initial_state)
        return result

    async def process_task_streaming(self, task_input: str, **kwargs) -> AsyncGenerator[dict, None]:
        """Yields state updates as the workflow progresses — for WebSocket streaming."""
        # Use LangGraph's astream_events or step-by-step execution
        # Yield after each node completes: {"node": "extract_information", "status": "complete", ...}
```

### 4.6 Integration Tests

`tests/integration/test_legal_intake_workflow.py`:

Test ALL 5 sample emails through the full workflow. For each, verify:
- Correct `qualification_decision`
- Appropriate `confidence_report.overall_score` range
- Brief generated with all required sections
- Audit trail has entries for every node
- No errors in state

```python
@pytest.mark.parametrize("email,expected_decision,min_confidence", [
    (CLEAR_QUALIFIED, "qualified", 0.8),
    (CLEAR_UNQUALIFIED, "not_qualified", 0.5),
    (AMBIGUOUS, "needs_review", 0.0),
    (POTENTIAL_CONFLICT, "qualified", 0.7),     # qualified but with conflict flag
    (URGENT, "qualified", 0.7),                  # qualified with urgency flag
])
async def test_intake_workflow(email, expected_decision, min_confidence):
    ...
```

---

## SPRINT 5: EMPLOYEE APP

### 5.1 Frontend Setup

`portal/employee_app/` — keep existing `electron/` and `package.json` scaffold. Add:
- Next.js 14+ App Router with TypeScript
- Tailwind CSS + shadcn/ui (button, input, textarea, card, badge, scroll-area, separator, tabs, avatar)
- WebSocket client hook

### 5.2 Expanded Employee API

Update `employee_runtime/core/api.py`:

```
POST   /api/v1/chat                    — send a chat message, returns streamed response
GET    /api/v1/chat/history             — paginated conversation history
POST   /api/v1/tasks                    — submit a task (email text) for workflow processing
GET    /api/v1/tasks/{id}               — task status + result
GET    /api/v1/tasks/{id}/brief         — the produced IntakeBrief
GET    /api/v1/activity                 — derived from audit_events, paginated
GET    /api/v1/approvals                — messages with type=approval_request where metadata.status=pending
POST   /api/v1/approvals/{id}/decide    — set decision (approve|decline|modify) in message metadata + audit
GET    /api/v1/settings                 — read from operational_memory pref: keys
PUT    /api/v1/settings                 — write to operational_memory pref: keys
GET    /api/v1/metrics                  — derived from audit_events: task count, avg confidence, approval mix, avg duration
WS     /api/v1/ws                       — WebSocket for streaming chat and task progress
```

### 5.3 App Components

**Layout:** Conversation (80% left) + Sidebar (20% right, collapsible)

**ChatView components:**
- `MessageBubble` — renders based on `message_type`:
  - `text`: plain text bubble
  - `brief_card`: renders IntakeBrief as structured card (see design below)
  - `approval_request`: card with Approve/Decline/Modify buttons
  - `status_update`: colored status badge
- `ChatInput` — textarea with send button + file drop zone
- `StreamingIndicator` — typing dots while employee is processing

**BriefCard design:**
```
┌─────────────────────────────────────────────┐
│ INTAKE BRIEF — #2024-0342                   │
│ Confidence: ████████░░ 87%                  │
├─────────────────────────────────────────────┤
│ CLIENT                                      │
│ Sarah Johnson · sarah.johnson@email.com     │
│ (555) 123-4567                              │
├─────────────────────────────────────────────┤
│ MATTER: Personal Injury — Car Accident      │
│ URGENCY: ● High                             │
│ VALUE: $73,000+                             │
├─────────────────────────────────────────────┤
│ KEY FACTS                                   │
│ • T-bone collision at Main & Broadway       │
│ • Broken collarbone + whiplash              │
│ • $45K medical bills, 6 weeks lost work     │
│ • Totaled 2022 Honda Civic ($28K)           │
├─────────────────────────────────────────────┤
│ ASSESSMENT                                  │
│ Qualified — Strong liability case with      │
│ clear damages. Recommend scheduling         │
│ consultation within 48 hours.               │
├─────────────────────────────────────────────┤
│ ⚠ FLAGS: None                              │
│ NEXT: Schedule consultation, request        │
│ police report, obtain medical records       │
├─────────────────────────────────────────────┤
│  [✓ Approve]   [✗ Decline]   [✎ Modify]   │
└─────────────────────────────────────────────┘
```

**Sidebar panels:**
- `InboxPanel` — queries `/approvals`, shows pending items with badge count
- `ActivityPanel` — queries `/activity`, shows timeline with timestamps
- `SettingsPanel` — queries/updates `/settings`: supervisor email, quiet hours, practice areas, firm name
- `MetricsPanel` — queries `/metrics`: tasks today/week/total, avg confidence, approval rate

### 5.4 First-Run Welcome

When conversation history is empty, display Arthur's introduction:

```
Hi Sarah, I'm Arthur — your legal intake associate.

I've been configured for Cartwright & Associates. I know your practice areas are
commercial litigation, employment law, and real estate.

Here's what I can do:
• Process intake emails — paste or type an email and I'll extract key information,
  check for conflicts, and produce a structured brief
• Qualify prospects — I'll assess whether a matter fits your firm's criteria
  and recommend next steps
• Morning briefings — I'll summarize activity and flag items needing your attention

You can paste an intake email here, or ask me anything. What would you like to start with?
```

### 5.5 WebSocket Streaming

Frontend connects via WebSocket. Chat flow:
1. User types message → sends via WebSocket: `{"type": "chat_message", "content": "Process this: ..."}`
2. Backend detects it's a task → runs workflow
3. Backend streams progress updates: `{"type": "status", "node": "extracting information..."}`
4. Backend streams the response tokens: `{"type": "token", "content": "Based on"}`
5. Backend sends completion: `{"type": "complete", "message_type": "brief_card", "data": {...}}`
6. Frontend renders the BriefCard

---

## SPRINT 6: POLISH + DEMO READINESS

### 6.1 Error Handling
- LLM timeout: retry 3x with exponential backoff (1s, 3s, 9s)
- Empty input: "I couldn't extract enough information. Could you provide more details?"
- Database error: queue task in Redis, retry when connection restores
- Confidence = 0: escalate with clear explanation
- All errors logged to audit trail with `event_type=error_occurred`

### 6.2 Morning Briefing
- Celery Beat schedule: configurable time (default 6:00 AM in client timezone)
- Compiles from audit events: tasks processed yesterday, pending approvals, items flagged for review
- Stored as a `system` message in conversation history
- Delivered via mock email to supervisor

### 6.3 Metrics
Derived from audit_events queries:
- Tasks processed: today / this week / all time (count events where `event_type=task_completed`)
- Average confidence: avg of `details.confidence` from `output_produced` events
- Approval rate: ratio of `approval_decided` events by decision type
- Average processing time: diff between `task_started` and `task_completed` timestamps

### 6.4 Demo Script
Run these 5 scenarios sequentially:
1. Open app → Arthur introduces himself
2. Paste CLEAR_QUALIFIED → streaming processing → BriefCard (87%+ confidence) → Approve
3. Paste AMBIGUOUS → processing → BriefCard with "needs_review" (60% confidence) → Modify
4. Paste POTENTIAL_CONFLICT → processing → BriefCard with conflict flag → Approve with note
5. Paste URGENT → processing → BriefCard with urgent flag → Approve
6. Show morning briefing in conversation
7. Open Activity → show timeline of all actions
8. Open Metrics → show task counts and confidence averages

Demo should run smoothly in 15 minutes.

---

## COMPLETION CHECKLIST

- [ ] Database: runtime tables exist via Alembic migration
- [ ] LLM: complete(), complete_structured(), stream() all work
- [ ] Router: multi-model routing with fallback
- [ ] Registry helper: creates component sets from config
- [ ] text_processor: extracts LegalIntakeExtraction from emails
- [ ] document_analyzer: produces qualification analysis
- [ ] draft_generator: produces readable IntakeBrief
- [ ] confidence_scorer: dual-mode scoring with ConfidenceReport
- [ ] audit_system: hash-chained event logging
- [ ] input_protection: catches prompt injection patterns
- [ ] verification_layer: validates brief completeness
- [ ] operational_memory: persistent fact storage in Postgres
- [ ] working_memory: task state in Redis
- [ ] context_assembler: builds LLM context within token budget
- [ ] org_context: organizational map with supervisor lookup
- [ ] email_tool: mock send/receive through ToolBroker
- [ ] LangGraph workflow: processes emails end-to-end with routing
- [ ] Employee API: all endpoints functional (chat, history, tasks, approvals, activity, settings, metrics, WebSocket)
- [ ] App: conversation interface with streaming responses
- [ ] App: BriefCard renders with Approve/Decline/Modify
- [ ] App: sidebar with Inbox (badge), Activity, Settings, Metrics
- [ ] App: first-run welcome message
- [ ] Morning briefing: scheduled and delivered
- [ ] Error handling: graceful on all failure paths
- [ ] All 5 sample emails process correctly
- [ ] Integration tests pass
- [ ] Demo runs smoothly for 15 minutes
