# FORGE V1 — PHASE 1 IN-DEPTH BUILD PLAN

## Phase 1 Goal

Hand-build a working Legal Intake Agent as modular components within the existing Forge scaffolding. At the end of Phase 1, a law firm partner can open the employee app, talk to Arthur, feed it intake emails, receive structured briefs with confidence scores, approve or decline, see the full audit trail, and receive a morning briefing.

## Starting State (Sprint 0 — Complete)

**What exists in Forge-apr8:**
- 80+ Python files across factory/, component_library/, employee_runtime/, tests/
- All 25 component stubs registered and categorized (but every `initialize()` and `execute()` is `pass`)
- Factory data models: `EmployeeRequirements`, `EmployeeBlueprint`, `SelectedComponent`, `CustomCodeSpec`, `Build` (with BuildStatus, BuildLog, BuildArtifact), `Deployment`, `ClientOrg`, `Client`, `MonitoringEvent`
- Employee runtime: `EmployeeEngine` (compiles LangGraph but no nodes), `EmployeeState` (task_id, input, context, outputs, errors, confidence, requires_human_approval), `ToolBroker` (permission check + audit log stub), employee API (health + task submit stub)
- Factory API: FastAPI with routes for health, commissions, builds, deployments, monitoring, roster — all returning stubs
- Pipeline worker: `start_pipeline()` wired as Architect → Builder (assemble → generate → package) → Evaluator → correction loop — all logging but not doing real work
- Docker Compose: Postgres 16 (pgvector), Redis 7, MinIO, factory service, pipeline worker
- Config: Pydantic Settings with all env vars, multi-model LLM routing (primary, fallback, reasoning, safety, fast via litellm)
- Tests: conftest with sample_org and sample_requirements fixtures, health endpoint test, registry tests, architect pipeline stubs
- Dockerfile: multi-stage build with factory target

**What does NOT exist:**
- No database tables (no ORM models, no Alembic migrations)
- No real LLM calls anywhere
- No real component implementations (all stubs)
- No workflow graph (LangGraph nodes not defined)
- No frontend code (portal directories have package.json only)
- No WebSocket support
- No real email integration
- No real memory persistence
- No real audit trail

---

## SPRINT 1: DATABASE + LLM FOUNDATION

**Duration:** 3–5 days
**Goal:** Database tables exist and migrate, LLM calls work through the component library, and you can get structured Pydantic responses from Claude.

### Task 1.1: SQLAlchemy ORM Models

**File:** `factory/models/orm.py` (new)

Create ORM models that map to the database. These are SEPARATE from the Pydantic models you already have — the Pydantic models are API/pipeline models, the ORM models are database models. They share field names but serve different purposes.

**Tables to create:**

```
clients
├── id: UUID (PK)
├── name: str
├── email: str
├── org_name: str
├── subscription_tier: str (enum: free, pro, enterprise)
├── created_at: datetime
└── updated_at: datetime

employee_requirements
├── id: UUID (PK)
├── client_id: UUID (FK → clients.id)
├── name: str
├── role_summary: text
├── data: JSONB (full EmployeeRequirements Pydantic model serialized)
├── status: str (enum: draft, confirmed, building, deployed)
├── created_at: datetime
└── updated_at: datetime

blueprints
├── id: UUID (PK)
├── requirements_id: UUID (FK → employee_requirements.id)
├── data: JSONB (full EmployeeBlueprint serialized)
├── created_at: datetime
└── updated_at: datetime

builds
├── id: UUID (PK)
├── blueprint_id: UUID (FK → blueprints.id)
├── client_id: UUID (FK → clients.id)
├── status: str (enum matching BuildStatus)
├── iteration: int (default 1)
├── logs: JSONB (array of BuildLog)
├── artifacts: JSONB (array of BuildArtifact)
├── test_report: JSONB
├── created_at: datetime
├── updated_at: datetime
└── completed_at: datetime | null

deployments
├── id: UUID (PK)
├── build_id: UUID (FK → builds.id)
├── client_id: UUID (FK → clients.id)
├── format: str (enum: web, desktop, server)
├── status: str (enum matching DeploymentStatus)
├── access_url: str
├── infrastructure: JSONB
├── created_at: datetime
├── activated_at: datetime | null
└── deactivated_at: datetime | null

audit_events
├── id: UUID (PK)
├── employee_id: str
├── tenant_id: str
├── event_type: str
├── details: JSONB
├── timestamp: datetime
├── prev_hash: str (hash of previous event — for chain integrity)
├── hash: str (SHA-256 of this event's content + prev_hash)
└── trace_id: str | null (links to LangFuse trace)

operational_memories
├── id: UUID (PK)
├── employee_id: str
├── tenant_id: str
├── key: str
├── value: JSONB
├── category: str (preference, contact, rule, decision, pattern)
├── created_at: datetime
├── updated_at: datetime
└── UNIQUE(employee_id, tenant_id, key)

conversations
├── id: UUID (PK)
├── employee_id: str
├── tenant_id: str
├── created_at: datetime
└── updated_at: datetime

messages
├── id: UUID (PK)
├── conversation_id: UUID (FK → conversations.id)
├── role: str (user, assistant, system)
├── content: text
├── message_type: str (text, brief_card, action_buttons, status_update, file)
├── metadata: JSONB (for rich content — brief data, button states, file refs)
├── created_at: datetime
└── INDEXED on (conversation_id, created_at)
```

**Implementation notes:**
- Use `sqlalchemy.orm.DeclarativeBase` for the base class
- Use `sqlalchemy.dialects.postgresql.UUID` and `JSONB` types
- Every table includes `tenant_id` where relevant for future multi-tenant isolation
- Add `__tablename__` explicitly for each model
- Create indexes on: `audit_events(employee_id, timestamp)`, `operational_memories(employee_id, tenant_id, key)`, `messages(conversation_id, created_at)`

**Update `factory/database.py`:**
- Add `create_tables()` function using `Base.metadata.create_all()`
- Update `init_engine()` to optionally auto-create tables when `AUTO_INIT_DB=true` (for dev)
- Ensure the async engine uses `create_async_engine` with `asyncpg`

### Task 1.2: Alembic Migration

**Files:** `alembic/versions/001_initial_schema.py` (auto-generated)

- Run `alembic revision --autogenerate -m "initial schema"`
- Review the generated migration — verify all tables, columns, indexes, and foreign keys
- Test: `docker-compose up -d postgres` → `alembic upgrade head` → verify tables exist using `psql`
- Add a `downgrade()` that drops all tables cleanly

### Task 1.3: LLM Provider Implementation

**File:** `component_library/models/anthropic_provider.py` (replace stub)

The current stub has `_model` hardcoded and no real LLM calls. Replace with:

```python
@register("anthropic_provider")
class AnthropicProvider(BaseComponent):
    component_id = "anthropic_provider"
    version = "1.0.0"
    category = "models"

    _model: str
    _client: Any  # litellm handles the client

    async def initialize(self, config: dict[str, Any]) -> None:
        self._model = config.get("model", "anthropic/claude-sonnet-4-20250514")
        # Verify API key is available
        settings = get_settings()
        if not settings.anthropic_api_key and not settings.openrouter_api_key:
            raise ValueError("No API key configured for Anthropic provider")

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Unstructured completion — returns raw text."""
        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content

    async def complete_structured(
        self,
        system_prompt: str,
        user_message: str,
        output_model: type[BaseModel],
        max_tokens: int = 4096,
    ) -> BaseModel:
        """Structured completion — returns a parsed Pydantic model."""
        client = instructor.from_litellm(litellm.acompletion)
        result = await client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_model=output_model,
            max_tokens=max_tokens,
        )
        return result

    async def health_check(self) -> ComponentHealth:
        try:
            resp = await self.complete("Say 'ok'.", "health check", max_tokens=5)
            return ComponentHealth(healthy=True, detail=f"model={self._model}")
        except Exception as e:
            return ComponentHealth(healthy=False, detail=str(e))
```

### Task 1.4: LiteLLM Router Implementation

**File:** `component_library/models/litellm_router.py` (replace stub)

The router selects the right model for each task type. It reads model names from config and routes accordingly.

```python
class TaskType(str, Enum):
    PRIMARY = "primary"         # Complex reasoning — Claude Sonnet
    FALLBACK = "fallback"       # Alternative reasoning — GPT-4o
    REASONING = "reasoning"     # Deep reasoning — o4-mini
    SAFETY = "safety"           # Safety checks — Claude Haiku
    FAST = "fast"               # Quick tasks — Claude Haiku
    EMBEDDING = "embedding"     # Embeddings — text-embedding-3-large

@register("litellm_router")
class LitellmRouter(BaseComponent):
    # Routes to the appropriate model based on TaskType
    # Tracks cost per call (model, input_tokens, output_tokens, estimated_cost)
    # Falls back to secondary model on failure
    # Integrates with LangFuse for tracing if configured
```

Key methods:
- `async def complete(task_type, system_prompt, user_message, **kwargs) -> str`
- `async def complete_structured(task_type, system_prompt, user_message, output_model, **kwargs) -> BaseModel`
- `async def embed(text) -> list[float]`
- Cost tracking: log every call with model, tokens, estimated cost via structlog

### Task 1.5: Tests for Sprint 1

**Files:**
- `tests/test_database.py` — verify tables are created, basic CRUD operations work
- `tests/components/models/test_anthropic_provider.py` — test real LLM calls (requires API key in env)
- `tests/components/models/test_litellm_router.py` — test routing logic, fallback behavior

**Acceptance criteria:**
- `docker-compose up -d` → all services healthy
- `alembic upgrade head` → all tables created
- `pytest tests/test_database.py` → tables exist, CRUD works
- `pytest tests/components/models/` → LLM calls return structured Pydantic outputs

### Claude Code Prompt for Sprint 1

```
Read CLAUDE.md and the existing codebase structure. Sprint 0 scaffolding is complete — all stubs exist but nothing is implemented.

Sprint 1 goal: Database tables + real LLM calls.

1. Create factory/models/orm.py with SQLAlchemy ORM models for: clients, employee_requirements, blueprints, builds, deployments, audit_events, operational_memories, conversations, messages. Use DeclarativeBase, async-compatible, JSONB for complex data, proper indexes.

2. Update factory/database.py to support auto-creating tables when AUTO_INIT_DB=true using the ORM models.

3. Create the initial Alembic migration.

4. Replace the anthropic_provider.py stub with a real implementation using litellm + instructor for structured output. Add complete() and complete_structured() methods.

5. Replace the litellm_router.py stub with a multi-model router that selects models by TaskType (primary, fallback, reasoning, safety, fast, embedding). Read model names from factory/config.py settings. Include cost tracking via structlog.

6. Write tests for database operations and LLM providers.

The existing factory/config.py already has: llm_primary_model, llm_fallback_model, llm_reasoning_model, llm_safety_model, llm_fast_model, embedding_model configured.
```

---

## SPRINT 2: CORE WORK CAPABILITIES

**Duration:** 3–5 days
**Goal:** text_processor and document_analyzer can read an intake email and extract structured legal data.

### Task 2.1: Enhance Component Interfaces for Work Capabilities

**File:** `component_library/interfaces.py` (modify)

The current `BaseComponent` has `initialize()`, `health_check()`, and `get_test_suite()`. Work capabilities need an `execute()` method. Rather than modifying `BaseComponent` (which all categories use), create a subclass:

```python
class WorkCapability(BaseComponent):
    """Base class for work capability components (Category 2)."""
    category = "work"

    @abstractmethod
    async def execute(self, input_data: BaseModel) -> BaseModel:
        """Execute the work capability.

        Args:
            input_data: Typed input (Pydantic model specific to this capability).

        Returns:
            Typed output (Pydantic model specific to this capability).
        """

class ToolIntegration(BaseComponent):
    """Base class for tool integration components (Category 3)."""
    category = "tools"

    @abstractmethod
    async def invoke(self, action: str, params: dict[str, Any]) -> dict[str, Any]:
        """Invoke a tool action."""

class DataSource(BaseComponent):
    """Base class for data source components (Category 4)."""
    category = "data"

    @abstractmethod
    async def query(self, query: str, **kwargs) -> Any:
        """Query the data source."""

class QualityModule(BaseComponent):
    """Base class for quality and governance components (Category 5)."""
    category = "quality"

    @abstractmethod
    async def evaluate(self, input_data: Any) -> BaseModel:
        """Evaluate input and return assessment."""
```

### Task 2.2: Define Input/Output Models for Legal Intake

**File:** `component_library/work/schemas.py` (new)

These Pydantic models define the structured data that flows through the legal intake workflow:

```python
class TextProcessorInput(BaseModel):
    """Input to the text_processor."""
    raw_text: str
    extraction_type: str = "general"  # general, legal_intake, email

class TextProcessorOutput(BaseModel):
    """Output from the text_processor."""
    extracted_fields: dict[str, Any]
    entities: list[dict[str, str]]  # [{name, type, value}]
    confidence: float
    raw_text_length: int

class LegalIntakeExtraction(BaseModel):
    """Structured extraction from a legal intake email."""
    client_name: str = ""
    client_email: str = ""
    client_phone: str = ""
    matter_type: str = ""  # e.g. "personal injury", "commercial litigation"
    date_of_incident: str = ""
    opposing_party: str = ""
    key_facts: list[str] = Field(default_factory=list)
    urgency: str = "normal"  # low, normal, high, urgent
    potential_conflicts: list[str] = Field(default_factory=list)
    estimated_value: str = ""
    referral_source: str = ""
    raw_summary: str = ""
    extraction_confidence: float = 0.0

class DocumentAnalyzerInput(BaseModel):
    """Input to the document_analyzer."""
    document_text: str
    analysis_type: str = "general"  # general, legal_intake, contract_review, summarize
    additional_context: str = ""

class DocumentAnalyzerOutput(BaseModel):
    """Output from the document_analyzer."""
    summary: str
    key_findings: list[str]
    entities: list[dict[str, str]]
    risk_flags: list[str]
    recommended_actions: list[str]
    confidence: float
    analysis_type: str

class IntakeBrief(BaseModel):
    """The complete intake brief produced for the supervising attorney."""
    brief_id: str = Field(default_factory=lambda: str(uuid4()))
    client_info: LegalIntakeExtraction
    analysis: DocumentAnalyzerOutput
    qualification_decision: str  # qualified, not_qualified, needs_review
    qualification_reasoning: str
    recommended_attorney: str = ""
    recommended_practice_area: str = ""
    next_steps: list[str] = Field(default_factory=list)
    confidence_score: float
    flags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Task 2.3: Implement text_processor

**File:** `component_library/work/text_processor.py` (replace stub)

The text_processor reads raw text (email, transcript, document) and extracts structured data. For legal intake, it extracts client info, case facts, and urgency.

**Implementation:**
- Inherits from `WorkCapability`
- Depends on `litellm_router` for LLM calls
- System prompt tailored to extraction type:
  - For `legal_intake`: "You are a legal intake specialist. Extract the following structured information from this client inquiry email: client name, email, phone, matter type, date of incident, opposing party, key facts, urgency level, potential conflicts, estimated case value, referral source."
- Uses `complete_structured()` with `LegalIntakeExtraction` as the output model
- Returns `TextProcessorOutput` with the extracted data and confidence

**The system prompt for legal intake extraction should be detailed:**
```
You are a legal intake processing specialist. Your job is to extract structured
information from client inquiry emails received by a law firm.

Extract the following fields. If a field is not mentioned, leave it empty.
Do not infer or fabricate information that is not explicitly stated.

- client_name: The full name of the prospective client
- client_email: Their email address
- client_phone: Their phone number
- matter_type: The type of legal matter (e.g., "personal injury", "employment discrimination", "commercial dispute", "family law", "real estate")
- date_of_incident: When the relevant event occurred
- opposing_party: The other party involved (person, company, or entity)
- key_facts: A list of the most important factual statements from the email
- urgency: "low" (no time pressure), "normal" (standard), "high" (approaching deadline), "urgent" (immediate action needed — e.g. statute of limitations)
- potential_conflicts: Names of any parties that should be checked for conflicts of interest
- estimated_value: Any mention of dollar amounts, damages, or financial impact
- referral_source: How they found the firm (if mentioned)
- raw_summary: A 2-3 sentence summary of the inquiry

Assign extraction_confidence between 0.0 and 1.0 based on:
- 0.9-1.0: All critical fields clearly stated
- 0.7-0.89: Most fields present but some ambiguity
- 0.5-0.69: Significant gaps or unclear information
- Below 0.5: Very incomplete or confusing inquiry
```

### Task 2.4: Implement document_analyzer

**File:** `component_library/work/document_analyzer.py` (replace stub)

For the legal intake workflow, the document_analyzer takes the extracted data from text_processor and produces a deeper analysis — qualification assessment, risk identification, and recommended actions.

**Implementation:**
- Inherits from `WorkCapability`
- Depends on `litellm_router`
- For `legal_intake` analysis type:
  - System prompt: "You are a senior legal intake analyst. Given the following extracted intake data, produce a qualification assessment: is this a matter the firm should pursue? Identify any risk flags. Recommend next steps."
  - Uses `complete_structured()` with `DocumentAnalyzerOutput`
  - Risk flags: statute of limitations concerns, conflict indicators, inadequate facts for assessment, potential fraud indicators, jurisdictional issues
  - Recommended actions: schedule consultation, request documentation, run conflicts check, decline with referral

### Task 2.5: Create Sample Intake Emails for Testing

**File:** `tests/fixtures/sample_emails.py` (new)

Create 5 sample intake emails covering different scenarios:

```python
CLEAR_QUALIFIED = """
Subject: Car Accident - Need Legal Help

Dear Attorney,

My name is Sarah Johnson and I was involved in a car accident on February 15, 2026
at the intersection of Main St and Broadway in Springfield. The other driver, James
Miller, ran a red light and T-boned my vehicle. I was taken to Springfield General
Hospital where I was treated for a broken collarbone and whiplash.

I've been unable to work for the past 6 weeks. My medical bills are currently at
$45,000 and climbing. My car was totaled — it was a 2022 Honda Civic worth about
$28,000.

I found your firm through a Google search. My phone number is (555) 123-4567 and
my email is sarah.johnson@email.com.

I'd like to schedule a consultation as soon as possible.

Thank you,
Sarah Johnson
"""

CLEAR_UNQUALIFIED = """..."""  # Matter outside firm's practice areas
AMBIGUOUS = """..."""          # Vague, missing key details
POTENTIAL_CONFLICT = """..."""  # Names a party the firm already represents
URGENT = """..."""             # Statute of limitations expiring in 2 weeks
```

### Task 2.6: Tests for Sprint 2

**Files:**
- `tests/components/work/test_text_processor.py` — feed each sample email through text_processor, verify LegalIntakeExtraction fields are populated correctly
- `tests/components/work/test_document_analyzer.py` — feed extraction output through document_analyzer, verify analysis quality
- `tests/components/work/test_schemas.py` — verify Pydantic models validate correctly, handle edge cases

**Key assertions:**
- CLEAR_QUALIFIED email: client_name="Sarah Johnson", matter_type contains "personal injury" or "car accident", urgency="normal" or "high", confidence >= 0.8
- CLEAR_UNQUALIFIED: qualification_decision="not_qualified"
- AMBIGUOUS: confidence < 0.7, risk_flags includes something about missing information
- POTENTIAL_CONFLICT: potential_conflicts list is non-empty
- URGENT: urgency="urgent", recommended_actions includes immediate attention

### Claude Code Prompt for Sprint 2

```
Read CLAUDE.md. Sprint 1 is complete — database tables exist, LLM calls work via anthropic_provider and litellm_router.

Sprint 2 goal: text_processor and document_analyzer that extract structured legal intake data.

1. Add subclass interfaces to component_library/interfaces.py: WorkCapability (with execute()), ToolIntegration (with invoke()), DataSource (with query()), QualityModule (with evaluate()).

2. Create component_library/work/schemas.py with Pydantic models: TextProcessorInput, TextProcessorOutput, LegalIntakeExtraction, DocumentAnalyzerInput, DocumentAnalyzerOutput, IntakeBrief.

3. Replace text_processor.py stub — implement using WorkCapability base class. Use litellm_router for LLM calls. For legal_intake extraction type, use a detailed system prompt that extracts all LegalIntakeExtraction fields. Use Instructor for structured output.

4. Replace document_analyzer.py stub — implement legal_intake analysis type that takes extracted data and produces qualification assessment, risk flags, and recommended actions.

5. Create tests/fixtures/sample_emails.py with 5 sample intake emails: clear qualified, clear unqualified, ambiguous, potential conflict, urgent.

6. Write tests that feed sample emails through both components and verify structured outputs.

Existing litellm_router has complete() and complete_structured() methods. Use complete_structured() with the schema models.
```

---

## SPRINT 3: MEMORY, COMMUNICATION, AND QUALITY

**Duration:** 5–7 days
**Goal:** The employee can persist facts, track current tasks, send emails, assess its own confidence, and maintain an immutable audit trail.

### Task 3.1: Implement operational_memory

**File:** `component_library/data/operational_memory.py` (replace stub)

Postgres-backed persistent fact store. This is the employee's long-term memory — what it knows about the client's business, preferences, contacts, and past decisions.

**Key methods:**
- `async def store(key, value, category)` — upsert a fact (ON CONFLICT UPDATE)
- `async def retrieve(key) -> dict | None` — get a specific fact
- `async def search(query, category=None, limit=20) -> list[dict]` — search facts by keyword in key or value
- `async def list_by_category(category) -> list[dict]` — get all facts of a type
- `async def delete(key)` — remove a fact

**Implementation notes:**
- Uses the `operational_memories` table from Sprint 1
- All operations scoped by `employee_id` + `tenant_id`
- Values stored as JSONB — can hold strings, numbers, lists, nested dicts
- Search uses PostgreSQL `ILIKE` on key and text search on JSONB value

### Task 3.2: Implement working_memory

**File:** `component_library/data/working_memory.py` (replace stub)

Redis-backed current task state. This is the employee's "scratchpad" — what it's working on right now.

**Key methods:**
- `async def set_context(task_id, key, value)` — store a value for the current task
- `async def get_context(task_id, key) -> Any` — retrieve
- `async def get_all_context(task_id) -> dict` — get everything for a task
- `async def clear_task(task_id)` — clean up after task completion

**Implementation notes:**
- Redis keys: `working_memory:{employee_id}:{task_id}:{key}`
- Default TTL: 24 hours (configurable)
- Values serialized as JSON
- Use `aioredis` or the `redis` package with async support

### Task 3.3: Implement context_assembler

**File:** `component_library/data/context_assembler.py` (replace stub)

Builds the LLM context window from all memory layers. This is critical — it determines what the LLM "knows" when processing a task.

**Key method:**
```python
async def assemble_context(
    task_input: str,
    employee_id: str,
    tenant_id: str,
    token_budget: int = 8000,
) -> str:
    """Build the complete context for an LLM call.

    Allocation:
    - System identity: ~800 tokens (who you are, your role, your rules)
    - Operational memory: ~1000 tokens (relevant known facts)
    - Conversation history: ~2000 tokens (recent messages)
    - Task input: variable (the current task)
    - Reserved for response: ~2000 tokens
    """
```

**Implementation:**
- Retrieves relevant operational memory facts by searching for keywords from the task input
- Retrieves recent conversation history (last N messages)
- Assembles into a structured context string:
  ```
  == YOUR IDENTITY ==
  You are Arthur, a Legal Intake Agent at [firm name]...

  == WHAT YOU KNOW ==
  - Client prefers email over phone
  - Practice areas: commercial litigation, employment, real estate
  - Partner Sarah Chen handles employment cases

  == RECENT CONVERSATION ==
  [last 5 messages]

  == CURRENT TASK ==
  [the task input]
  ```
- Uses a simple token counting heuristic (word_count * 1.3) to stay within budget
- Truncates least relevant content if over budget (oldest conversation messages first, then least relevant memory facts)

### Task 3.4: Implement email_tool

**File:** `component_library/tools/email_tool.py` (replace stub)

V1 uses Python's built-in `imaplib` and `smtplib` for simplicity. This avoids the Composio dependency for now.

**Key methods:**
- `async def monitor_inbox(criteria, limit) -> list[EmailMessage]` — check for new emails matching criteria
- `async def send_email(to, subject, body, cc=None, attachments=None)` — send an email
- `async def reply_to(original_message_id, body)` — reply to a specific email
- `async def mark_read(message_id)` — mark as read after processing

**Implementation:**
- Inherits from `ToolIntegration`
- All calls go through the ToolBroker (the email_tool doesn't call IMAP directly — it returns the action parameters to the ToolBroker, which enforces permissions and logs the call)
- Config: `email_address`, `imap_server`, `smtp_server`, `email_password` (from env vars for V1)
- For V1, use `aiosmtplib` for async SMTP and wrap `imaplib` with `asyncio.to_thread()` for async IMAP
- Define `EmailMessage` Pydantic model: id, from_addr, to_addr, subject, body, date, attachments

**Alternative for V1 (simpler):** Skip real IMAP/SMTP entirely. Create a `MockEmailTool` that reads from a file or API endpoint. The demo uses the mock. Real email integration comes in Sprint 6 polish or post-Phase 1. This keeps Sprint 3 focused on the harder components (memory, context assembly, audit).

### Task 3.5: Implement confidence_scorer

**File:** `component_library/quality/confidence_scorer.py` (replace stub)

Two-mode confidence assessment:

**Mode 1: LLM Self-Assessment**
Ask the model to rate its own confidence on a specific output. System prompt:
```
You are a quality assessor. Rate your confidence in the following output on a scale of 0.0 to 1.0.
Consider: Are all required fields present? Are the extractions supported by the source text?
Are there any ambiguities or assumptions? Rate each dimension separately, then provide an overall score.
```

**Mode 2: Structural Assessment**
Programmatic checks (no LLM needed):
- Are all required fields populated? (+0.2 per critical field present)
- Is the text length reasonable? (not too short, not suspiciously long)
- Are dates in valid format?
- Are phone numbers/emails in valid format?
- Are there any contradiction indicators?

**Output:**
```python
class ConfidenceReport(BaseModel):
    overall_score: float  # 0.0 - 1.0
    llm_self_assessment: float
    structural_score: float
    dimension_scores: dict[str, float]  # {completeness, consistency, specificity, ...}
    flags: list[str]  # specific concerns identified
    recommendation: str  # "proceed", "review", "escalate"
```

### Task 3.6: Implement audit_system

**File:** `component_library/quality/audit_system.py` (replace stub)

Immutable, hash-chained event logging.

**Key methods:**
- `async def log_event(employee_id, tenant_id, event_type, details) -> AuditEvent` — create and store an audit event
- `async def get_trail(employee_id, since=None, event_type=None) -> list[AuditEvent]` — retrieve audit trail
- `async def verify_chain(employee_id) -> ChainVerification` — verify hash chain integrity

**Hash-chaining implementation:**
```python
async def log_event(self, employee_id, tenant_id, event_type, details):
    # Get the previous event's hash
    prev = await self._get_latest_event(employee_id, tenant_id)
    prev_hash = prev.hash if prev else "genesis"

    # Create the event
    event = AuditEvent(
        employee_id=employee_id,
        tenant_id=tenant_id,
        event_type=event_type,
        details=details,
        timestamp=datetime.utcnow(),
        prev_hash=prev_hash,
    )

    # Compute hash: SHA-256 of (event_type + details_json + timestamp_iso + prev_hash)
    content = f"{event.event_type}|{json.dumps(event.details, sort_keys=True)}|{event.timestamp.isoformat()}|{event.prev_hash}"
    event.hash = hashlib.sha256(content.encode()).hexdigest()

    # Store (append-only — never update or delete)
    await self._insert_event(event)
    return event
```

**Event types for V1:**
- `task_created`, `task_started`, `task_completed`, `task_failed`
- `llm_called` (model, tokens, cost)
- `tool_invoked` (tool_id, action, parameters)
- `output_produced` (output_type, confidence)
- `approval_requested`, `approval_decided` (approved/declined/modified)
- `memory_stored`, `memory_updated`
- `error_occurred`

### Task 3.7: Implement org_context

**File:** `component_library/data/org_context.py` (replace stub)

The organizational map — who the employee reports to, who its colleagues are, and how to communicate with each person.

**Implementation:**
```python
class Person(BaseModel):
    name: str
    role: str
    email: str
    communication_preference: str = "email"  # email, slack, formal, casual
    relationship: str = "colleague"  # supervisor, colleague, client, vendor

class OrgContext(DataSource):
    """Organizational context — the employee's social map."""

    async def initialize(self, config):
        self._people = {p["name"]: Person(**p) for p in config.get("people", [])}
        self._escalation_chain = config.get("escalation_chain", [])
        self._firm_name = config.get("firm_name", "")
        self._practice_areas = config.get("practice_areas", [])

    async def get_supervisor(self) -> Person | None
    async def get_escalation_chain(self) -> list[Person]
    async def get_person(self, name) -> Person | None
    async def get_firm_info(self) -> dict
    async def query(self, query, **kwargs) -> str  # natural language lookup
```

### Task 3.8: Tests for Sprint 3

**Test files:**
- `tests/components/data/test_operational_memory.py` — store, retrieve, search, category filtering
- `tests/components/data/test_working_memory.py` — set, get, clear, TTL expiry
- `tests/components/data/test_context_assembler.py` — verify context is assembled within token budget, relevant facts included
- `tests/components/quality/test_confidence_scorer.py` — both modes produce valid ConfidenceReport
- `tests/components/quality/test_audit_system.py` — events logged, hash chain valid, chain verification passes, tampering detected
- `tests/components/data/test_org_context.py` — supervisor lookup, escalation chain, person lookup

### Claude Code Prompt for Sprint 3

```
Read CLAUDE.md. Sprints 1-2 complete — database tables exist, LLM calls work, text_processor and document_analyzer produce structured legal intake data.

Sprint 3 goal: Memory persistence, email (mock for now), confidence scoring, and immutable audit trail.

1. Replace operational_memory.py — Postgres-backed persistent fact store with store/retrieve/search/list_by_category. Uses the operational_memories table. All operations scoped by employee_id + tenant_id.

2. Replace working_memory.py — Redis-backed task state with set_context/get_context/clear_task. Keys: working_memory:{employee_id}:{task_id}:{key}. 24hr TTL.

3. Replace context_assembler.py — builds LLM context from operational memory + conversation history + task input. Token budget management with allocation: 800 system identity, 1000 operational memory, 2000 conversation, variable task input.

4. Create a MockEmailTool for V1 (reads from fixtures) — real IMAP/SMTP comes later.

5. Replace confidence_scorer.py — two modes: LLM self-assessment and structural checks (field completeness, format validity). Produces a ConfidenceReport with overall score, dimension scores, and recommendation.

6. Replace audit_system.py — append-only Postgres logging with SHA-256 hash-chaining. log_event, get_trail, verify_chain. Event types: task_created, task_started, llm_called, tool_invoked, output_produced, approval_requested, etc.

7. Replace org_context.py — organizational map with Person model, supervisor lookup, escalation chain.

8. Write tests for each component.

Use the existing async database engine from factory/database.py and Redis connection from factory/config.py settings.
```

---

## SPRINT 4: THE LEGAL INTAKE WORKFLOW

**Duration:** 4–6 days
**Goal:** Wire all components into a LangGraph workflow that processes an intake email end-to-end, producing a structured brief.

### Task 4.1: Define the Workflow Graph

**File:** `employee_runtime/workflows/legal_intake.py` (new)

This is the core — the LangGraph `StateGraph` that defines how the employee processes an intake.

**Graph structure:**
```
START
  → sanitize_input          (input_protection — check for injection)
  → extract_information      (text_processor — extract structured data)
  → analyze_intake          (document_analyzer — produce analysis)
  → score_confidence        (confidence_scorer — assess quality)
  → route_by_confidence     (conditional routing)
      ├── [confidence >= 0.85] → generate_brief → queue_for_delivery
      ├── [0.4 <= conf < 0.85] → flag_for_review → generate_brief → queue_for_delivery
      └── [confidence < 0.4]   → escalate → queue_for_delivery
  → deliver_to_supervisor   (send brief via email or app notification)
  → log_completion          (audit trail)
END
```

**Each node is a function that:**
1. Receives the `EmployeeState`
2. Reads what it needs from state
3. Calls the appropriate component
4. Writes results back to state
5. Logs the action to the audit system
6. Returns the updated state

### Task 4.2: Enhance EmployeeState

**File:** `employee_runtime/core/state.py` (modify)

The current `EmployeeState` is too generic. Add legal intake specific fields while keeping it extensible:

```python
class EmployeeState(TypedDict):
    """State passed between nodes in the employee workflow graph."""
    # Core
    task_id: str
    employee_id: str
    tenant_id: str

    # Input
    raw_input: str
    input_type: str  # email, form, api, transcript
    input_metadata: dict  # sender, subject, received_at, etc.

    # Processing
    extracted_data: dict  # output of text_processor
    analysis: dict        # output of document_analyzer
    confidence_report: dict  # output of confidence_scorer

    # Decision
    qualification_decision: str  # qualified, not_qualified, needs_review, escalated
    qualification_reasoning: str

    # Output
    brief: dict           # the IntakeBrief
    delivery_method: str  # email, app_notification, both
    delivery_status: str  # pending, sent, failed

    # Meta
    errors: list[str]
    audit_trail: list[str]  # list of audit event IDs
    requires_human_approval: bool
    escalation_reason: str
    started_at: str
    completed_at: str
```

**Important:** Use `TypedDict` instead of Pydantic BaseModel for LangGraph state — LangGraph requires this.

### Task 4.3: Implement Each Workflow Node

**File:** `employee_runtime/workflows/legal_intake.py`

Each node follows this pattern:

```python
async def extract_information(state: EmployeeState) -> EmployeeState:
    """Node: extract structured data from the raw input."""
    # Get components (injected via config)
    text_proc = get_component_instance("text_processor")
    audit = get_component_instance("audit_system")

    # Log start
    await audit.log_event(
        state["employee_id"], state["tenant_id"],
        "task_stage_started", {"stage": "extract_information"}
    )

    # Execute
    input_data = TextProcessorInput(
        raw_text=state["raw_input"],
        extraction_type="legal_intake"
    )
    result = await text_proc.execute(input_data)

    # Update state
    state["extracted_data"] = result.model_dump()

    # Log completion
    await audit.log_event(
        state["employee_id"], state["tenant_id"],
        "output_produced",
        {"stage": "extract_information", "confidence": result.confidence}
    )

    return state
```

**Implement ALL nodes:**
1. `sanitize_input` — runs input through input_protection, rejects if injection detected
2. `extract_information` — text_processor with type="legal_intake"
3. `analyze_intake` — document_analyzer with type="legal_intake"
4. `score_confidence` — confidence_scorer on the analysis output
5. `route_by_confidence` — conditional edge based on confidence score
6. `generate_brief` — draft_generator produces IntakeBrief
7. `flag_for_review` — sets requires_human_approval=True with reason
8. `escalate` — sets escalation_reason, sets requires_human_approval=True
9. `deliver_to_supervisor` — sends brief (via mock email or stores for app)
10. `log_completion` — final audit event

### Task 4.4: Implement draft_generator

**File:** `component_library/work/draft_generator.py` (replace stub)

Produces a formatted, readable intake brief from structured data.

**For "intake_brief" type:**
- Takes: LegalIntakeExtraction + DocumentAnalyzerOutput + ConfidenceReport
- Produces: IntakeBrief (the complete brief with all sections)
- The LLM generates the narrative sections (qualification_reasoning, recommended next steps) while the structured data is passed through directly
- System prompt: "You are a senior legal intake coordinator. Given the following extracted client information and analysis, produce a concise intake brief for the supervising attorney. Focus on actionable information. Be clear about what is known, what is uncertain, and what requires the attorney's judgment."

### Task 4.5: Implement input_protection (basic)

**File:** `component_library/quality/input_protection.py` (replace stub)

V1 implementation — pattern matching, not ML-based:

```python
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+a",
    r"disregard\s+(all\s+)?prior",
    r"new\s+instructions?\s*:",
    r"system\s*:\s*",
    r"<\s*/?system\s*>",
    # ... more patterns
]

class InputProtectionResult(BaseModel):
    is_safe: bool
    risk_score: float  # 0.0 (safe) to 1.0 (dangerous)
    flags: list[str]
    sanitized_input: str
```

### Task 4.6: Wire EmployeeEngine to Run the Workflow

**File:** `employee_runtime/core/engine.py` (modify)

Update the engine to build and run the legal intake graph:

```python
class EmployeeEngine:
    def __init__(self, workflow_name: str, components: dict[str, BaseComponent], config: dict):
        self._components = components
        self._config = config
        self._graph = self._build_graph(workflow_name)
        self._app = self._graph.compile()

    def _build_graph(self, workflow_name: str) -> StateGraph:
        if workflow_name == "legal_intake":
            from employee_runtime.workflows.legal_intake import build_legal_intake_graph
            return build_legal_intake_graph(self._components)
        raise ValueError(f"Unknown workflow: {workflow_name}")

    async def process_task(self, task_input: str, input_type: str = "email", metadata: dict = None) -> dict:
        """Process a task through the workflow."""
        initial_state = {
            "task_id": str(uuid4()),
            "employee_id": self._config["employee_id"],
            "tenant_id": self._config["tenant_id"],
            "raw_input": task_input,
            "input_type": input_type,
            "input_metadata": metadata or {},
            # ... initialize all other state fields with defaults
        }
        result = await self._app.ainvoke(initial_state)
        return result
```

### Task 4.7: End-to-End Integration Test

**File:** `tests/integration/test_legal_intake_workflow.py`

This is the most important test in Phase 1:

```python
async def test_full_intake_workflow():
    """Feed a sample email through the complete legal intake workflow."""
    # Setup: initialize all components with test config
    components = {
        "text_processor": TextProcessor(),
        "document_analyzer": DocumentAnalyzer(),
        "confidence_scorer": ConfidenceScorer(),
        "draft_generator": DraftGenerator(),
        "input_protection": InputProtection(),
        "audit_system": AuditSystem(),
    }
    for comp in components.values():
        await comp.initialize(test_config)

    # Build and run
    engine = EmployeeEngine("legal_intake", components, employee_config)
    result = await engine.process_task(CLEAR_QUALIFIED_EMAIL, input_type="email")

    # Assertions
    assert result["qualification_decision"] == "qualified"
    assert result["confidence_report"]["overall_score"] >= 0.8
    assert "Sarah Johnson" in str(result["extracted_data"])
    assert result["brief"] is not None
    assert len(result["audit_trail"]) >= 5  # at least 5 audit events
    assert result["errors"] == []
```

**Run against ALL 5 sample emails** and verify appropriate outcomes for each.

### Claude Code Prompt for Sprint 4

```
Read CLAUDE.md. Sprints 1-3 complete — database, LLM, text_processor, document_analyzer, memory, confidence_scorer, audit_system all working.

Sprint 4 goal: Wire everything into a LangGraph workflow that processes intake emails end-to-end.

1. Create employee_runtime/workflows/legal_intake.py with a LangGraph StateGraph. Nodes: sanitize_input, extract_information, analyze_intake, score_confidence, route_by_confidence (conditional), generate_brief, flag_for_review, escalate, deliver_to_supervisor, log_completion.

2. Update employee_runtime/core/state.py — use TypedDict (required by LangGraph). Add all fields: raw_input, extracted_data, analysis, confidence_report, qualification_decision, brief, delivery_status, errors, audit_trail, requires_human_approval.

3. Implement draft_generator.py — produces a formatted IntakeBrief from extraction + analysis + confidence data.

4. Implement input_protection.py — basic regex pattern matching for prompt injection detection.

5. Update EmployeeEngine to build the legal_intake graph from workflow definition, injecting components into nodes.

6. Write a comprehensive integration test that feeds all 5 sample emails through the full workflow and verifies: correct qualification decisions, appropriate confidence scores, brief generation, audit trail completeness.

Every node must log to audit_system. Routing: confidence >= 0.85 auto-qualifies, 0.4-0.85 flags for review, <0.4 escalates.
```

---

## SPRINT 5: THE EMPLOYEE APP

**Duration:** 7–10 days
**Goal:** A Next.js frontend where the client talks to Arthur and sees his work.

### Task 5.1: Initialize the Next.js App

**Directory:** `portal/employee_app/`

```bash
npx create-next-app@latest portal/employee_app --typescript --tailwind --eslint --app --src-dir
cd portal/employee_app
npx shadcn@latest init
npx shadcn@latest add button input textarea card badge scroll-area separator tabs avatar
npm install lucide-react
```

### Task 5.2: Employee API — Expand Endpoints

**File:** `employee_runtime/core/api.py` (major expansion)

The current API has `/health` and a stub `/tasks`. Expand to:

```
POST   /api/v1/chat                    — send a message, get streaming response
GET    /api/v1/chat/history             — conversation history (paginated)
POST   /api/v1/tasks                    — submit a task for processing
GET    /api/v1/tasks/{id}               — check task status
GET    /api/v1/tasks/{id}/brief         — get the produced brief
GET    /api/v1/activity                 — activity timeline (paginated)
GET    /api/v1/approvals                — pending approval items
POST   /api/v1/approvals/{id}/decide    — approve/decline/modify
GET    /api/v1/documents                — list processed documents
GET    /api/v1/metrics                  — basic performance metrics
GET    /api/v1/settings                 — current settings
PUT    /api/v1/settings                 — update settings
WS     /api/v1/ws                       — WebSocket for real-time streaming
```

**WebSocket implementation:**
```python
@app.websocket("/api/v1/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_json()
        if data["type"] == "chat_message":
            # Process through the engine
            # Stream response tokens back via websocket
            async for chunk in engine.process_streaming(data["content"]):
                await websocket.send_json({"type": "token", "content": chunk})
            await websocket.send_json({"type": "complete"})
```

### Task 5.3: Build the Chat Interface

**File:** `portal/employee_app/src/app/page.tsx` and components

The main view: conversation on the left (80%), sidebar on the right (20%).

**Components to build:**
- `ChatView` — the main conversation area
- `MessageBubble` — renders a single message (text, brief card, action buttons)
- `ChatInput` — text input with send button, file drop zone
- `BriefCard` — renders an IntakeBrief as a structured card with sections
- `ApprovalButtons` — Approve / Decline / Modify buttons on items requiring approval
- `Sidebar` — collapsible navigation with Inbox, Activity, Documents, Settings
- `InboxPanel` — list of pending approvals with badge count
- `ActivityPanel` — timeline of employee actions
- `SettingsPanel` — basic employee configuration

**BriefCard rendering:**
```
┌────────────────────────────────────────┐
│ INTAKE BRIEF — #2024-0342              │
│ Confidence: 92%  ●●●●●●●●●○           │
├────────────────────────────────────────┤
│ CLIENT: Sarah Johnson                  │
│ MATTER: Personal Injury — Car Accident │
│ URGENCY: High                          │
│ ESTIMATED VALUE: $73,000+              │
├────────────────────────────────────────┤
│ KEY FACTS:                             │
│ • T-bone collision at Main & Broadway  │
│ • Broken collarbone + whiplash         │
│ • $45K medical bills, 6 weeks missed   │
│ • Totaled 2022 Honda Civic ($28K)      │
├────────────────────────────────────────┤
│ RECOMMENDATION: Qualified — Schedule   │
│ consultation. Strong liability case.   │
├────────────────────────────────────────┤
│ [✓ Approve]  [✗ Decline]  [✎ Modify] │
└────────────────────────────────────────┘
```

### Task 5.4: Real-Time Streaming

The chat interface should show the employee "thinking" — tokens streaming in real-time, not a single response block appearing after 10 seconds.

**Frontend:** WebSocket connection in a React hook. Messages stream token by token. A typing indicator shows while the employee is processing.

**Backend:** The engine's `process_streaming()` method yields tokens as they come from the LLM. The WebSocket relay sends each chunk to the frontend.

### Task 5.5: First-Run Experience

When the app first opens (no conversation history), Arthur introduces himself:

```
Hi Sarah, I'm Arthur — your legal intake associate.

I've been configured for Cartwright & Associates. I know your practice
areas are commercial litigation, employment law, and real estate.

Here's what I can do:
• Process intake emails — I'll extract key information, check for
  conflicts, and produce a structured brief
• Qualify prospects — I'll assess whether a matter fits your firm's
  criteria
• Morning briefings — I'll summarize overnight activity each morning

You can paste an intake email here, or ask me anything about my capabilities.

What would you like to start with?
```

### Task 5.6: File/Email Input in Chat

The client should be able to:
- Paste an email directly into the chat ("Process this: [email text]")
- Drag and drop a file (.eml, .txt, .pdf) into the chat
- Forward an email to a processing address (post-V1)

For V1, support text paste and basic file upload (txt only). PDF parsing comes later.

### Claude Code Prompt for Sprint 5

```
Read CLAUDE.md. Sprints 1-4 complete — the legal intake workflow processes emails end-to-end with structured briefs, confidence scoring, and audit trail.

Sprint 5 goal: Build the employee app frontend.

1. The Next.js app is initialized in portal/employee_app/. Set up Tailwind + shadcn/ui.

2. Build the main layout: ChatView (80% left) + Sidebar (20% right, collapsible).

3. Build ChatView with: MessageBubble (text, brief_card, action_buttons types), ChatInput (text + file drop), streaming response display via WebSocket.

4. Build BriefCard component — renders an IntakeBrief as a structured card with client info, key facts, recommendation, confidence bar, and Approve/Decline/Modify buttons.

5. Build Sidebar with: InboxPanel (pending approvals with badge), ActivityPanel (timeline), SettingsPanel (basic config: name, quiet hours, supervisor email).

6. Expand employee_runtime/core/api.py with: POST /chat, GET /chat/history, GET /activity, GET /approvals, POST /approvals/{id}/decide, GET /settings, PUT /settings, WebSocket /ws endpoint.

7. Add first-run welcome message.

8. Connect frontend to API — WebSocket for chat streaming, REST for everything else.

The frontend should feel like Claude Desktop or ChatGPT — clean, conversational, immediate.
```

---

## SPRINT 6: POLISH + DEMO READINESS

**Duration:** 5–7 days
**Goal:** Everything works reliably enough to demonstrate to a law firm partner.

### Task 6.1: Verification Layer

**File:** `component_library/quality/verification_layer.py` (replace stub)

Basic output verification:
- Schema validation: does the IntakeBrief have all required fields populated?
- Format validation: are dates valid? phone numbers plausible? email addresses formatted correctly?
- Consistency checks: does the urgency match the facts (e.g., urgent should have a time-sensitive element)?
- Completeness scoring: what percentage of fields are filled?

### Task 6.2: Morning Briefing (Celery Beat)

**Implementation:**
- Add Celery Beat schedule in `factory/workers/celery_app.py`
- Create `employee_runtime/modules/morning_briefing.py`
- The briefing compiles: tasks processed yesterday, pending approvals, items flagged for review, any anomalies
- Delivered as a structured message in the app conversation AND as an email to the supervisor

### Task 6.3: Error Handling Hardening

Test and fix every error path:
- LLM timeout → retry with exponential backoff (3 attempts)
- Empty or garbled email → graceful message: "I couldn't extract enough information from this email. Could you provide more details?"
- Database connection lost → queue task in Redis, retry when connection restores
- Confidence = 0 → escalate with clear explanation
- All errors logged to audit trail

### Task 6.4: Demo Scenario Suite

Create a scripted demo using the 5 sample emails + morning briefing:

1. Open the app. Arthur says hello.
2. Paste CLEAR_QUALIFIED email. Watch Arthur process it (streaming). See the BriefCard appear with 92% confidence. Click Approve.
3. Paste AMBIGUOUS email. Arthur processes it, flags for review (65% confidence). Brief shows specific uncertainties. Click Modify → add clarifying info.
4. Paste POTENTIAL_CONFLICT email. Arthur processes it, flags the conflict. Brief warns about the conflict with red flag.
5. Paste URGENT email. Arthur processes it, marks as urgent, recommends immediate action.
6. Show the morning briefing: "Good morning, Sarah. Yesterday: 4 intakes processed, 2 approved, 1 pending review, 1 escalated. Today's priority: follow up on the urgent matter."
7. Open the Activity timeline — show all actions with timestamps.
8. Open an activity detail — show the full reasoning record.
9. Show Settings — quiet hours, supervisor email, practice areas.

### Task 6.5: Basic Metrics

Add to the Metrics tab in the sidebar:
- Tasks processed: today / this week / all time
- Average confidence score
- Approval rate (approved / modified / declined / escalated)
- Average processing time

### Task 6.6: Visual Polish

- Loading states: skeleton UI while waiting for API
- Error states: friendly error messages
- Empty states: helpful prompts when no data exists
- Mobile responsiveness: basic responsive layout (not required for demo but nice to have)
- Consistent spacing, typography, and color scheme

### Claude Code Prompt for Sprint 6

```
Read CLAUDE.md. Sprints 1-5 complete — full workflow + app frontend working.

Sprint 6 goal: Polish for demo readiness.

1. Implement verification_layer.py — schema validation, format validation, consistency checks on IntakeBrief output.

2. Add morning briefing via Celery Beat — daily scheduled task that compiles yesterday's activity and sends to the app conversation + email.

3. Harden error handling: LLM timeouts (retry x3), empty input (graceful message), database errors (queue in Redis), zero confidence (escalate with explanation). All errors logged to audit.

4. Add metrics to the app: tasks processed, average confidence, approval rate, average processing time.

5. Visual polish: loading skeletons, error states, empty states, consistent styling.

6. Run the 5-scenario demo suite end-to-end. Fix anything that breaks. The demo should take 15 minutes and tell a complete story.
```

---

## PHASE 1 COMPLETION CHECKLIST

When Phase 1 is done, ALL of the following must be true:

- [ ] `docker-compose up` starts all services (Postgres, Redis, MinIO, factory)
- [ ] Database tables created via Alembic migration
- [ ] LLM calls work through anthropic_provider and litellm_router
- [ ] text_processor extracts structured LegalIntakeExtraction from emails
- [ ] document_analyzer produces qualification analysis
- [ ] confidence_scorer rates output quality (dual-mode)
- [ ] audit_system logs every action with hash-chaining
- [ ] input_protection catches basic prompt injection
- [ ] verification_layer validates output completeness
- [ ] operational_memory persists facts in Postgres
- [ ] working_memory tracks task state in Redis
- [ ] context_assembler builds LLM context within token budgets
- [ ] org_context provides organizational map
- [ ] draft_generator produces readable intake briefs
- [ ] LangGraph workflow processes emails end-to-end
- [ ] Employee app conversation interface works (send message → streaming response)
- [ ] BriefCard renders with Approve/Decline/Modify buttons
- [ ] Sidebar shows: Inbox (with badge), Activity, Settings
- [ ] WebSocket streaming works for real-time responses
- [ ] First-run welcome message displays
- [ ] Morning briefing scheduled and delivered
- [ ] Error handling doesn't crash the system
- [ ] 5 sample emails process correctly with appropriate outcomes
- [ ] All integration tests pass
- [ ] Demo runs smoothly for 15 minutes

**When this checklist is complete, you have a product to show law firms.**
