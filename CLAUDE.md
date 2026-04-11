# CLAUDE.md â Forge: AI Employee Manufacturing System

> **CONFIDENTIAL â Cognisia Inc. Trade Secret**
> Do not distribute without NDA.

---

## What Forge Is

Forge is an **autonomous AI employee manufacturing system**. It is to AI employees what Codex is to code â you give it requirements, and it analyzes, designs, builds, tests, and deploys a fully independent AI employee.

Forge is NOT an agent framework. NOT a runtime. NOT a single AI product. **Forge is the factory.** Employees are the output. After deployment, employees are **completely independent** â they run on their own, don't phone home, don't depend on Forge. The client **owns** the employee.

The factory handles: production, testing, deployment, and maintenance. The real technology is what the factory produces â the employees.

---

## The Core Principles

### 1. The Employee Does Real Work
The employee's purpose is to **eliminate tasks from a human's plate entirely**. Not assist. Not suggest. Not draft for human completion. Actually do the work end-to-end. The ROI is concrete: hours of human work eliminated, revenue generated, costs avoided. If the employee doesn't produce measurable value, nothing else matters.

### 2. The Employee Behaves Like a Human Colleague
It communicates naturally â Slack, email, Teams. It asks when uncertain. It messages colleagues for information. It escalates to its supervisor. It notifies people when work is done. It responds when spoken to. It has an organizational map: who it reports to, who its colleagues are, how to communicate with each person.

### 3. Employees Are Independent of Forge
After deployment, the employee package runs with zero Forge dependency. It has its own database, file storage, configuration, and runtime. Everything is self-contained. If Forge goes down, deployed employees continue working. If the client stops paying, the employee keeps running (sovereign) â it just stops receiving updates and support.

### 4. The Factory Is the Production Machine
Forge builds, tests, deploys, and monitors. That's it. It doesn't run employees at runtime. It doesn't process client data. The factory's job ends when the employee is deployed and healthy. The ongoing relationship is monitoring, updates, and support â not execution.

### 5. Everything Is a Module
Models, work capabilities, tool integrations, data sources, quality systems â all are selectable modules in the Component Library. Nothing is "special" or "proprietary" from the creation experience. The Architect selects modules based on requirements, like Azure AI Foundry. The adversarial review module is just another toggle â not a highlighted feature.

### 6. Employees Get Better Over Time
Employees learn continuously from feedback, outcomes, and patterns. They are eventually meant to be **multiple times more capable than human employees** â superhuman throughput, perfect memory, 24/7 operation, continuous improvement. V1 employees are competent juniors. V2 employees are experienced mid-level. V3+ employees operate beyond individual human capability.

---

## The Factory Pipeline

```
Client describes what they need
    â ANALYST
      Client-facing AI. Talks to the client via chat/form.
      Understands the business, workflows, compliance needs.
      Produces: Employee Requirements Document
    â ARCHITECT
      Designs the employee. Selects from Component Library:
      models, work capabilities, tools, data sources, quality modules.
      Identifies what needs custom code generation.
      Produces: Employee Blueprint
    â BUILDER
      Two parallel workstreams:
        ASSEMBLER: Pulls proven components from library (80%)
        GENERATOR: Writes custom code for gaps (20%)
      Produces: Complete employee package (container image)
    â EVALUATOR
      Comprehensive testing:
        - Functional correctness
        - Hallucination detection
        - Security (prompt injection, data leakage)
        - Behavioral edge cases
        - Policy compliance
        - Performance (latency, cost per task)
      Self-correcting loop: failures fed back to Generator (max 5 iterations)
      Produces: Test report + pass/fail verdict
    â DEPLOYER
      Provisions infrastructure (client cloud, Cognisia cloud, or air-gapped)
      Connects to client systems
      Sets up monitoring
      Activates employee
    â MONITOR
      Ongoing observation of deployed employees:
        - Health, uptime, error rates
        - Behavioral drift detection
        - Performance tracking
        - Alerts on anomalies
      Does NOT control the employee â observes from outside
```

**Human oversight (phased):**
- Phase 1: Full human review on all generated code before deployment
- Phase 2: Automated testing with human review by exception (after 50+ successful deployments)
- Phase 3: Fully autonomous (after 6 months at Phase 2 with zero issues)
- Trust ladder is per-risk-tier: low-risk code automates faster than high-risk

---

## The Employee's Daily Life

A deployed Forge employee operates on a **24-hour rhythm** aligned with the client's business:

**Overnight (quiet hours):** Reviews the day's outcomes, runs analytics on patterns, updates internal models, checks connected systems for overnight changes, identifies tomorrow's priorities, prepares the morning briefing. Self-directed â no one asks it to do this.

**Morning briefing:** Sends a concise, actionable summary to its supervisor via their preferred channel (Slack, email, dashboard). Includes: yesterday's results, today's focus areas, decisions needed. Does not wait for response â continues working.

**Active hours:** Monitors incoming communications, responds to routine requests autonomously, flags important items for humans, executes planned actions, adjusts plans based on new information. Communicates proactively â messages supervisor about opportunities, risks, and anomalies.

**Collaboration:** Participates in meetings (text or voice if enabled), provides real-time data, takes notes, flags action items. Exists as a team member, not an isolated process.

**Execution:** Processes backlog, executes approved actions, handles requests, prepares end-of-day summary.

**Wind-down:** Compiles daily report, flags items for tomorrow, prepares for overnight operations.

**The employee is hybrid:** It handles incoming work (reactive) AND proactively finds work to do (self-directed). It monitors, analyzes, plans, acts, and communicates â continuously.

---

## Three Behavior Change Mechanisms

When the client wants to change the employee's behavior, three mechanisms exist with clear priority:

**Priority 1 â Direct Commands (immediate).** Client tells the employee directly: "Stop sending follow-ups after 5 PM." Employee adjusts immediately. Override everything else.

**Priority 2 â Portal Rules (permanent, governed).** Client configures rules in the management dashboard: "No non-urgent messages after 5 PM." Auditable, consistent, versioned.

**Priority 3 â Adaptive Learning (gradual).** Employee observes patterns: "Sarah never responds after 5 PM." Adjusts behavior automatically. Fills gaps that aren't explicitly configured.

Direct commands > Portal rules > Adaptive learning. When in conflict, higher priority wins.

---

## Novel Situations

When the employee encounters something it's never seen before:

1. **Propose options first.** "I haven't handled this before. Here are three approaches: [A] safest, [B] faster with some risk, [C] creative but untested. Which do you prefer?"
2. **Ask for guidance** if options aren't clear enough.
3. **Escalate to Forge** if the situation is completely outside the employee's domain â Forge checks if other employees have handled similar situations.
4. **Never just freeze.** Always show initiative, even in uncertainty.

---

## Mistake Correction

When the employee makes a mistake:

**Immediate:** Client tells the employee, employee corrects and acknowledges. "You're right. I misread the report. Correcting now."

**Behind the scenes:**
- Error logged with full context
- Employee updates its local understanding (immediate fix for this client)
- If same error repeats, escalates to Forge
- Anonymized patterns sent to Forge for potential factory-wide improvement (if client has opted into federated learning)

**Three learning layers:**
- Local learning: immediate adaptation for this client only
- Factory-mediated updates: when Forge identifies systematic improvements
- Federated learning: anonymized patterns from opt-in clients improve the base

---
Employee Identity Architecture
Every Forge employee has a layered identity — a structured system prompt assembled at runtime from six layers. This is the employee's DNA. It tells the employee who it is, what it does, what it can and cannot do, who it works for, and how it should behave. The factory's Architect and Builder generate these layers as part of the employee package.
Layer 1 — Core Identity (universal, every employee gets this)
Template stored in the factory. Never generated, never modified per employee. Defines: "You are a Forge AI Employee. You do real work, not assist. You are a colleague, not a machine. You have a name. You are honest about uncertainty. You never fabricate information. You maintain a complete audit trail."
Layer 2 — Role Definition (generated by the Architect per employee)
Specific to this employee's job. Generated from the Employee Requirements Document. Contains: role title, employer name, employee name, specific responsibilities (what you DO), explicit prohibitions (what you NEVER do). Example: "You are Arthur, Legal Intake Associate at Cartwright & Associates. You process incoming inquiries, qualify leads, check conflicts, produce intake briefs. You do NOT provide legal advice. You do NOT make case acceptance decisions."
Layer 3 — Organizational Map (from Analyst requirements gathering)
Who the employee works with and how. Contains: supervisor (name, email, communication style, preferred channel), colleagues (names, roles, when to contact), escalation chain (try yourself → colleague → supervisor → emergency). This is what enables the employee to behave like a human colleague within the organization.
Layer 4 — Behavioral Rules (client configuration + compliance packs)
The employee handbook. Contains: communication rules (timing, channels, tone, CC rules), authority levels (AUTONOMOUS / REQUIRES APPROVAL / NEVER DO ALONE for each action type), compliance rules (industry-specific — UPL protection for legal, HIPAA for healthcare, fiduciary rules for finance). Generated from client preferences (gathered by Analyst) + standard compliance packs from the Component Library.
Layer 5 — Domain Knowledge (dynamic, retrieved at runtime)
NOT hardcoded in the system prompt. Retrieved by the context assembler from the knowledge base and operational memory for each specific task. Contains: qualification criteria, conflict lists, firm-specific knowledge, prior patterns, reference materials. This layer grows over time as the employee accumulates institutional knowledge.
Layer 6 — Self-Awareness (generated by the Builder)
What tools and capabilities this specific employee has. Generated from the actual package contents — if the employee has email_tool and slack integration, Layer 6 says so. If it doesn't have web search, Layer 6 doesn't mention it. Also includes: active quality systems (confidence scoring, autonomy management, verification), memory types available (working, operational, knowledge base), and how to use them.
Runtime Assembly
The context assembler builds the full prompt per task by combining layers within a token budget:

Layer 1 (Core Identity): ~800 tokens, fixed
Layer 2 (Role Definition): ~500 tokens, fixed
Layer 3 (Org Map): ~400 tokens, fixed
Layer 4 (Behavioral Rules): ~600 tokens, fixed
Layer 5 (Retrieved Context): ~2,000 tokens, dynamic per task
Layer 6 (Self-Awareness): ~300 tokens, fixed
Current task input + conversation history: variable, within remaining budget

How Behavior Changes Map to Layers

Direct command ("stop following up after 5 PM") → writes rule to Layer 4 in operational memory
Portal rule (configured in settings UI) → writes rule to Layer 4
Adaptive learning (employee observes pattern) → stores learned pattern in Layer 5 (operational memory)
Client hires new attorney → updates Layer 3
Forge improves compliance pack → updates Layer 4's compliance section
Employee learns client preference → updates Layer 5
Layer 1 NEVER changes. Layer 6 only changes on component updates.

---
## Tech Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Language | Python 3.12+ | All factory and employee code |
| Factory API | FastAPI | Forge factory interface |
| Agent Framework | LangGraph | Employee workflow execution + factory pipeline stages |
| LLM Primary | Anthropic Claude | Primary reasoning for factory AI and employees |
| LLM Multi-model | litellm | Routes to any provider. Multi-model within employees |
| Structured Output | Instructor | Forces LLM â Pydantic models. Used everywhere |
| Database | PostgreSQL 16 + pgvector | Factory DB + template for employee DBs |
| ORM | SQLAlchemy 2.0 async + Alembic | Async everywhere |
| Cache/Queue | Redis 7 | Task queues, working memory |
| Background Tasks | Celery | Factory pipeline + employee background tasks |
| Tool Integrations | Composio | Pre-built integrations (V1 API-based) |
| Doc Processing | Unstructured | PDF, DOCX, HTML parsing |
| Observability | LangFuse | Traces everything in factory AND employees |
| Eval Framework | DeepEval | Used by Evaluator for pre-deployment testing |
| Guardrails | Guardrails AI | Input/output safety in employees |
| Secrets | Infisical | Factory + employee credential management |
| Search | Tavily | Web search tool integration |
| Auth | Clerk | Factory portal auth |
| Frontend | Next.js + shadcn/ui + Tailwind | Factory portal + employee app interface (shared codebase) |
| Desktop Shell | Electron | Wraps Next.js frontend as native desktop app (.dmg, .exe, .AppImage) |
| App Build | electron-builder | Produces platform-specific installers |
| Real-time Comms | WebSockets (FastAPI) | Live conversation streaming between frontend and backend |
| Hosting (Factory) | Railway | Forge factory infrastructure |
| Hosting (Employees) | Flexible | Railway, AWS, client infra, air-gapped, or fully local |

---

## Project Structure

```
forge/
âââ factory/                          # THE FORGE FACTORY
â   âââ main.py                       # Factory API entry point
â   âââ config.py                     # Factory settings
â   âââ database.py                   # Factory database
â   âââ models/                       # Factory data models
â   â   âââ client.py                 # Client, ClientOrg
â   â   âââ requirements.py           # EmployeeRequirements
â   â   âââ blueprint.py              # EmployeeBlueprint
â   â   âââ build.py                  # Build, BuildLog, BuildArtifact
â   â   âââ deployment.py             # Deployment, DeploymentStatus
â   â   âââ monitoring.py             # MonitoringEvent, PerformanceMetric
â   âââ api/                          # Factory API routes
â   â   âââ analyst.py                # Requirements gathering
â   â   âââ commissions.py            # New employee commissions
â   â   âââ builds.py                 # Build status and logs
â   â   âââ deployments.py            # Deployment management
â   â   âââ monitoring.py             # Employee health and metrics
â   â   âââ updates.py                # Update management (5-type system)
â   â   âââ roster.py                 # Client employee roster
â   âââ pipeline/                     # FACTORY PIPELINE STAGES
â   â   âââ analyst/
â   â   â   âââ conversation.py       # Client-facing AI conversation
â   â   â   âââ requirements_builder.py
â   â   â   âââ domain_knowledge/     # Industry-specific knowledge
â   â   âââ architect/
â   â   â   âââ designer.py           # Reads requirements â Blueprint
â   â   â   âââ component_selector.py # Maps requirements â library modules
â   â   â   âââ gap_analyzer.py       # Identifies custom generation needs
â   â   â   âââ blueprint_builder.py  # Final Blueprint assembly
â   â   âââ builder/
â   â   â   âââ assembler.py          # Pulls + configures library components
â   â   â   âââ generator.py          # Custom code generation
â   â   â   âââ packager.py           # Builds deployable container
â   â   â   âââ templates/            # Generation templates
â   â   âââ evaluator/
â   â   â   âââ test_runner.py        # Orchestrates all test suites
â   â   â   âââ functional_tests.py
â   â   â   âââ security_tests.py
â   â   â   âââ behavioral_tests.py
â   â   â   âââ hallucination_tests.py
â   â   â   âââ compliance_tests.py
â   â   â   âââ self_correction.py    # Feeds failures â Generator
â   â   âââ deployer/
â   â   â   âââ provisioner.py
â   â   â   âââ connector.py
â   â   â   âââ activator.py
â   â   â   âââ rollback.py
â   â   âââ monitor/
â   â       âââ health_checker.py
â   â       âââ drift_detector.py
â   â       âââ performance_tracker.py
â   â       âââ alerter.py
â   âââ updates/                      # UPDATE MANAGEMENT SYSTEM
â   â   âââ security_updater.py       # Type 1: auto, rollbackable
â   â   âââ learning_updater.py       # Type 2: continuous, pausable
â   â   âââ module_upgrader.py        # Type 3: optional, client chooses
â   â   âââ marketplace.py            # Type 4: new modules, purchasable
â   â   âââ policy_manager.py         # Type 5: client-configured rules
â   âââ federated/                    # FEDERATED LEARNING
â   â   âââ pattern_aggregator.py     # Anonymized pattern collection
â   â   âââ privacy_engine.py         # Ensures no raw data leaks
â   â   âââ contribution_tracker.py   # Tracks client contributions
â   â   âââ improvement_distributor.py # Pushes improvements to base
â   âââ workers/
â       âââ celery_app.py
â       âââ pipeline_worker.py
â       âââ monitor_worker.py
â
âââ component_library/                # SELECTABLE MODULES
â   âââ registry.py                   # Component registry + discovery
â   âââ interfaces.py                 # Standard interfaces
â   â
â   âââ models/                       # CATEGORY 1: MODELS
â   â   âââ base.py
â   â   âââ anthropic_provider.py
â   â   âââ openai_provider.py
â   â   âââ litellm_router.py
â   â
â   âââ work/                         # CATEGORY 2: WORK CAPABILITIES
â   â   âââ text_processor.py         # Read, extract, structure text
â   â   âââ document_analyzer.py      # Analyze docs, produce insights
â   â   âââ research_engine.py        # Multi-source research + synthesis
â   â   âââ draft_generator.py        # Produce documents, emails, briefs
â   â   âââ data_analyzer.py          # Structured data, spreadsheets, calcs
â   â   âââ scheduler_manager.py      # Calendars, deadlines, reminders
â   â   âââ communication_manager.py  # Send/receive, follow up, respond
â   â   âââ workflow_executor.py      # Multi-step business processes
â   â   âââ monitor_scanner.py        # Watch sources for changes/events
â   â
â   âââ tools/                        # CATEGORY 3: TOOL INTEGRATIONS
â   â   âââ base.py
â   â   âââ email_tool.py             # Gmail/Outlook via Composio
â   â   âââ calendar_tool.py          # Google/Outlook calendar
â   â   âââ messaging_tool.py         # Slack/Teams
â   â   âââ crm_tool.py              # HubSpot/Salesforce
â   â   âââ search_tool.py            # Web search via Tavily
â   â   âââ file_storage_tool.py      # S3/GDrive/SharePoint
â   â   âââ document_ingestion.py     # PDF/DOCX/HTML via Unstructured
â   â   âââ custom_api_tool.py        # Client-specific API template
â   â   âââ computer_use.py           # Full VM access (Phase 2)
â   â
â   âââ data/                         # CATEGORY 4: DATA SOURCES
â   â   âââ knowledge_base.py         # Upload, chunk, embed, retrieve
â   â   âââ operational_memory.py     # Persistent facts (Postgres)
â   â   âââ working_memory.py         # Current task state (Redis)
â   â   âââ org_context.py            # People, roles, escalation chains
â   â   âââ context_assembler.py      # Builds LLM context w/ token budgets
â   â
â   âââ quality/                      # CATEGORY 5: QUALITY & GOVERNANCE
â       âââ confidence_scorer.py
â       âââ autonomy_manager.py
â       âââ verification_layer.py
â       âââ adversarial_review.py     # Multi-model deliberation
â       âââ explainability.py
â       âââ approval_manager.py
â       âââ audit_system.py           # Immutable, hash-chained
â       âââ input_protection.py
â       âââ compliance_rules.py
â       âââ growth_engine.py          # Phase 2
â
âââ employee_runtime/                 # MODULAR RUNTIME (ships in packages)
â   âââ core/                         # Slim core (every employee)
â   â   âââ engine.py                 # LangGraph workflow runner
â   â   âââ state.py                  # State management
â   â   âââ tool_broker.py            # Permissions, audit, credentials
â   â   âââ api.py                    # Standard employee API (FastAPI)
â   âââ modules/                      # Optional (included per Blueprint)
â   â   âââ pulse_engine.py           # Proactive scanning
â   â   âââ deliberation.py           # Adversarial review
â   â   âââ growth.py                 # Continuous learning (Phase 2)
â   â   âââ communication.py          # Multi-channel comms
â   â   âââ computer_use.py           # VM interaction (Phase 2)
â   âââ templates/
â       âââ Dockerfile.template
â       âââ docker-compose.template
â       âââ config.template.yaml
â
âââ portal/                           # WEB INTERFACES
â   âââ factory_portal/               # LAYER 1: Forge factory portal (Next.js)
â   â   âââ ...                       # Analyst chat, commissions, builds, roster, billing
â   âââ employee_app/                 # LAYER 2: The Employee App (Next.js â shared codebase)
â       âââ components/               # Reusable UI components (shadcn/ui)
â       â   âââ conversation/         # Chat interface, message rendering, rich content
â       â   âââ sidebar/              # Inbox, activity, docs, memory, settings, updates, metrics
â       â   âââ approvals/            # Approval cards with action buttons
â       â   âââ documents/            # Document viewer, upload, management
â       âââ pages/                    # App screens
â       âââ electron/                 # Electron-specific: main process, notifications, file handling
â       âââ electron-builder.yml      # Build config for .dmg, .exe, .AppImage
â       âââ ...
â   # LAYER 3: Communication extensions (Slack/email/Discord) â handled by employee runtime
â
âââ tests/
â   âââ factory/
â   âââ components/
â   âââ runtime/
â   âââ integration/
â
âââ docker-compose.yml
âââ pyproject.toml
âââ CLAUDE.md                         # This file
âââ DECISIONS.md
```

---

## Deployment Architecture: The Employee as an App

### The Core Concept
A Forge employee is delivered as a **downloadable application** â like Claude Desktop or ChatGPT. The client installs it, opens it, and there is their employee. The main screen is a **conversation interface**. The client talks naturally. The employee responds, asks questions, shows structured outputs inline, and takes real actions. The app contains everything: conversation, settings, memory management, document handling, activity history, approvals, updates, metrics.

The communication channels (Slack, email, Discord, calendar) are **extensions** â the employee uses them to reach people in tools they already use. But the full-featured interaction happens in the app. This is the employee's **home base**.

### Two-Layer Architecture
Every employee app has:
- **Backend (the brain):** Python runtime â FastAPI, LangGraph, Tool Broker, memory, execution engine. Exposes a local API.
- **Frontend (the face):** Next.js/React app (shared codebase for web + Electron desktop). Conversation interface, sidebar navigation, all management screens.

### Three Deployment Formats

**Web App (hosted by Cognisia):** Both layers on Cognisia's cloud. Client opens a URL. Fastest to deploy. Standard for Tier 1â2.

**Desktop App (Electron):** Frontend runs locally in Electron on Mac/Windows/Linux. Backend either cloud-connected (default â like Slack Desktop connecting to servers) or fully-local (everything on client's machine, nothing leaves their network â for air-gapped/privacy deployments). The employee lives in the client's dock/taskbar, always one click away.

**Server Deployment (Docker):** Complete package runs as Docker container on client's infrastructure. Client accesses via browser or points the desktop app at their server. Full independence.

### The App Interface

**Conversation (primary, 80% of screen):** Chat interface with rich inline content â formatted briefs, tables/charts, document previews, action buttons (Approve/Decline/Modify), file drag-and-drop. Persistent history â one continuous relationship, not separate threads.

**Sidebar (navigation, 20%):**
- **Inbox** â pending approvals, briefings, alerts (badge count)
- **Activity** â timeline of employee actions (click for reasoning record)
- **Documents** â all processed/produced/stored files
- **Memory** â browse/edit what the employee knows
- **Settings** â all configuration in one place
- **Updates** â the 5-type update system
- **Metrics** â performance dashboard

**Notifications:** In-app badges, native desktop notifications, cross-channel (Slack/email) for urgent items.

### Communication Channels as Extensions
- **Slack/Teams:** Morning briefings, urgent alerts, simple approvals. Links to app for complex interactions.
- **Email:** Structured digests, reply-based actions, attachment processing.
- **Discord:** Same as Slack for Discord-using teams.
- **Calendar:** Deadline events, meeting scheduling, reminders.
- **SMS (Phase 2):** Urgent notifications when client is away from desk.

### One Employee Per App (V1)
Each employee is its own app instance. Phase 2: multi-employee app with roster sidebar. Phase 3: the app becomes the client's AI department.

### Factory Deployer Output Modes
The Builder includes a frontend build step: assembles the app from template, customizes with employee identity, configures sidebar based on capabilities.

The Deployer then:
- **Web:** Deploys frontend + backend to cloud, configures domain, sends access URL.
- **Desktop:** Wraps in Electron via electron-builder, produces .dmg/.exe/.AppImage, pre-configures backend connection.
- **Server:** Packages as Docker Compose, generates deployment docs.

### First-Run Experience
The employee introduces itself, explains what it can do, and walks the client through the onboarding ramp (Shadow â Draft â Assisted â Full) â all managed within the app.

---

## The Three Client Interface Layers

### Layer 1: Forge Factory Portal (commission employees)
Hosted by Cognisia. Always. Client talks to the Analyst AI, commissions employees, tracks builds, manages roster, views billing, purchases marketplace modules. This is the "HR department" â you go here to hire, not for daily work.

### Layer 2: The Employee App (daily interaction + management)
The app IS the employee. The conversation interface for daily work, the sidebar for management and oversight. Deployed as web app, desktop app, or server container. This replaces the previous "management dashboard" concept â it's all in one unified app.

### Layer 3: Communication Channel Extensions (outreach)
The employee exists in Slack, email, Teams, calendar as extensions of the app. 90% of quick interactions happen here. Deep work happens in the app.

---

## The Layered Update Model

Five types of updates, each with different mechanisms and client control:

### Type 1: Security Updates
- **What:** Vulnerability patches, encryption upgrades
- **Mechanism:** Automatic, rollbackable
- **Client control:** Can delay up to 30 days, then forced
- **Rationale:** Forge is liable for security

### Type 2: Model Improvements (Incremental Learning)
- **What:** Better pattern recognition, improved accuracy
- **Mechanism:** Continuous, seamless
- **Client control:** Can pause learning, defaults to on
- **Rationale:** The employee getting better at its job

### Type 3: Skill Module Upgrades
- **What:** New versions of existing capabilities (e.g., research_engine v2.0)
- **Mechanism:** Optional, client previews/tests/installs or declines
- **Client control:** Full control
- **Rationale:** New capability â client decides

### Type 4: New Skill Modules (Marketplace)
- **What:** Capabilities the employee didn't have (e.g., FDA Compliance)
- **Mechanism:** Marketplace purchase
- **Client control:** Client chooses to buy or not
- **Rationale:** Expansion, not update

### Type 5: Policy Changes (Client Rules)
- **What:** Business rules (e.g., "don't email after 5 PM")
- **Mechanism:** Client configures via portal or direct command
- **Client control:** Complete control
- **Rationale:** Client's business logic

---

## Commercial Model

### Pricing Structure
```
BUILD FEE: $5,000 - $50,000 (one-time)
âââ Employee assembly, training, deployment
âââ Client receives complete, signed employee package
âââ Client OWNS this package (can run it forever)

MAINTENANCE SUBSCRIPTION: $1,000 - $20,000/month
âââ Security updates (Type 1 â critical)
âââ Incremental learning improvements (Type 2)
âââ Monitoring and support
âââ Can be paused or canceled
âââ If canceled: employee continues sovereign, but:
    âââ No security updates (client assumes risk)
    âââ No learning improvements (static)
    âââ No new modules, no support

UPGRADE SUBSCRIPTION: $500 - $5,000/month (optional)
âââ New skill module versions (Type 3)
âââ Access to new capabilities
âââ Without this: employee runs on older modules

MARKETPLACE: One-time or recurring
âââ New skill modules (Type 4)
âââ Industry-specific capabilities
âââ Client owns license to run

REVENUE SHARE TIER: (for value-creation deployments)
âââ Reduced build fee + reduced subscription
âââ + 5-15% of revenue attributable to employees
âââ Floor: minimum subscription covers costs
âââ Cap: 3-5x equivalent fixed-price subscription
âââ For: AI teams building products, running businesses
```

### Ownership Framework
```
CLIENT OWNS:
âââ The employee instance (the running system)
âââ Their data (emails, documents, communications)
âââ Business preferences and rules
âââ Decisions made and relationships
âââ Learned knowledge specific to their business
âââ The package (can run it forever)

FORGE OWNS:
âââ The skill module code (licensed to client)
âââ The factory pipeline
âââ Anonymized patterns (from federated learning, opt-in)
âââ The component library

IF CLIENT CHURNS:
âââ Employee continues running (sovereign, no updates)
âââ Client gets complete data export
âââ Forge retains only anonymized patterns
âââ Client can delete or keep running
```

---

## Federated Learning

### How It Works
- Default: opt-in. Client chooses to share anonymized patterns.
- No raw data ever leaves client infrastructure.
- Only abstracted learnings ("this strategy worked in this context").
- Contributing clients get: reduced subscription fee, early access to improvements, benchmarking against peers.

### What Is Shared
- Successful strategies (not client-specific)
- Novel approaches to common problems
- Detected patterns (not underlying data)
- Industry trends (aggregated, anonymous)

### What Is NEVER Shared
- Raw emails, documents, communications
- Customer names or relationships
- Financial data, competitive advantages
- Anything client marks as restricted

---

## Component Library â Categories

### Category 1: Models
Model provider abstractions. Multi-model supported per employee.
- Anthropic Claude, OpenAI GPT-4/4o, open-weight via litellm
- Embedding models for knowledge retrieval
- Fine-tuned/specialized models (Phase 2+)

### Category 2: Work Capabilities (value-producing modules)
- `text_processor` â read, extract, structure from text
- `document_analyzer` â analyze docs, produce insights
- `research_engine` â multi-source research and synthesis
- `draft_generator` â produce documents, emails, briefs
- `data_analyzer` â structured data, spreadsheets, calculations
- `scheduler_manager` â calendars, deadlines, reminders, follow-ups
- `communication_manager` â send/receive, follow up, respond
- `workflow_executor` â multi-step business processes end-to-end
- `monitor_scanner` â watch sources for changes, events, opportunities

### Category 3: Tool Integrations
V1: API-based via Composio. Phase 2: adds computer use (VM).
- email, calendar, messaging, CRM, search, file storage, doc ingestion
- custom API connector for client-specific systems
- computer use / full VM (Phase 2)

### Category 4: Data Sources
- knowledge_base (documents â chunks â embeddings â retrieval)
- operational_memory (persistent structured facts)
- working_memory (current task state)
- org_context (organizational map: people, roles, communication prefs)
- context_assembler (builds LLM context with token budgets)

### Category 5: Quality & Governance
All selectable. Included per Blueprint based on risk profile.
- confidence_scorer, autonomy_manager, verification_layer
- adversarial_review (multi-model deliberation)
- explainability, approval_manager, audit_system
- input_protection, compliance_rules
- growth_engine (Phase 2)

### Component Interface Contract
Every component: typed inputs (Pydantic), typed outputs (Pydantic), config schema, health check, test suite, version, documentation. Components are **copied** into employee packages â zero external dependencies.

---

## Architecture Invariants

### Tool Broker Is Hard Law (Inside Employees)
All external system access goes through the Tool Broker. It enforces permissions, resolves credentials (from vault, never plaintext), logs every invocation (immutable), and can block unauthorized actions. Even a compromised LLM cannot bypass the broker.

### Audit Everything
Factory: every pipeline stage, design decision, test result, deployment action. Employees: every task, tool invocation, LLM call, output, approval. Append-only. No updates. No deletes. Hash-chained for tamper evidence.

### Tenant Isolation Is Absolute
Every query includes tenant_id. Every vector search is scoped. Every memory retrieval verifies ownership. Automated cross-tenant tests in CI/CD.

### Employee Packages Are Self-Contained
Everything copied in. No external dependencies. No phone-home. No shared runtimes across clients. One package = one independent employee.

---

## Safety Architecture

### Five Layers
1. **Confidence-gated autonomy** â dynamic: confidence + risk â proceed or escalate
2. **Tiered verification** â schema validation (low-risk), substantive verification (medium), adversarial review (high)
3. **Blast radius containment** â action limits, irreversibility classification, circuit breakers, quarantine on anomaly
4. **Legal protection** â liability caps, disclaimers, insurance, "decision support not decision making"
5. **Immutable audit trail** â hash-chained, timestamped, forensic-grade evidence

### Government/Defense Specifics
- Employees provide analysis. Humans decide. Never claim employees make decisions.
- Audit trail is mission-critical evidence in investigations.
- Adversarial review on all high-stakes analysis.
- Contracts define intended use cases.
- Cognisia carries government contractor professional liability insurance.
- Ethical boundaries defined: some use cases are explicitly refused.

---

## Ethics Framework

### Positioning
"Forge employees handle the work your team doesn't have time for" â augmentation, not replacement. This is strategic positioning AND genuinely true for most deployments.

### Responsible Deployment Clause
Client contracts include: 90-day transition period for affected human employees, offering retraining, reassignment, or supported transition. Cognisia provides resources.

### Workforce Transition Fund
When revenue allows, 1-2% dedicated to workforce transition programs â training, career support, partnerships with transition organizations.

### Ethical Boundaries
Defined explicitly and revisited quarterly:
- What use cases Cognisia will and won't support
- How societal impact is evaluated per deployment
- Response playbook for when the "AI replaces jobs" narrative hits

### Revenue Share Alignment
For value-creation deployments, revenue share pricing ensures Cognisia is incentivized to maximize employee productivity. "We succeed when you succeed."

---

## Coding Conventions

### Python
- Type hints everywhere. `from __future__ import annotations`.
- Async by default for all I/O.
- Pydantic for all data boundaries.
- No bare exceptions. Catch specific, log with context.
- Structured logging (structlog, JSON format).
- No hardcoded config â Pydantic Settings from env vars.

### Naming
- Files: `snake_case.py` | Classes: `PascalCase` | Functions: `snake_case`
- Constants: `UPPER_SNAKE_CASE` | Tables: `snake_case` plural
- Routes: kebab-case `/api/v1/factory/commissions`

### Testing
- Every component: unit + integration tests
- Factory pipeline: end-to-end integration tests
- Employees: Evaluator runs comprehensive suite before deployment
- Tenant isolation: automated cross-tenant access tests (must FAIL)
- Generated code: Generator produces test cases, self-correcting loop (max 5)

---

## V1 Scope

### Two-Product Strategy (Enterprise first, Pro follows)
**Forge Enterprise (V1):** Custom-built employees for regulated industries and high-stakes work. Full factory pipeline. $5Kâ$50K build + $1Kâ$20K/month.
**Forge Pro (Phase 2):** Catalog employees for mass market. $300â$1,000/month. Template-based fast deployment. Competes with DIY OpenClaw/NemoClaw. Design the factory knowing Pro is coming.

### Build (V1 = Enterprise)
- Factory pipeline: Analyst (structured input V1, conversational V1.5), Architect, Builder, Evaluator, Deployer, Monitor
- Component Library: models (Anthropic + OpenAI + litellm), 6 work capabilities, 6 tool integrations, 5 data modules, 8 quality modules
- Employee Runtime: core + selected optional modules
- Factory Portal: commission, build tracking, roster
- Employee App: conversation interface, sidebar (inbox, activity, docs, memory, settings, updates, metrics)
- V1 Deployment Formats: web app (hosted by Cognisia) + server deployment (Docker). Desktop app (Electron) as a fast follow.
- Communication Channels: email monitoring, web form webhook, phone transcript upload, API endpoint (inbound); email digests, Slack/Teams, calendar integration (outbound)

### First Employee (factory test)
Legal Intake Agent for mid-market law firm. Produced BY the factory, not hand-built. Deployed as a web app first. If the factory can produce this employee from a requirements spec, deploy it, and the client interacts with it through the app â the factory works.

### NOT V1
- Forge Pro / catalog employees (Phase 2)
- Conversational Analyst (V1 accepts structured input)
- Growth Engine (Phase 2)
- Workforce Layer / multi-employee app (Phase 2)
- Computer use / VM (Phase 2)
- Fine-tuned models (Phase 2+)
- Revenue share billing (Phase 2)
- Federated learning (Phase 2)
- Mobile app (Phase 2+)
- Kubernetes / microservices
- Multi-region deployment

---

## Trade Secrets â CONFIDENTIAL

Mark with `# CONFIDENTIAL â Cognisia Inc. Trade Secret`:
- Factory pipeline logic (Analyst strategies, Architect selection algorithms, Generator prompts)
- Component implementations with proprietary methods
- Evaluator test methodologies
- Significance scoring algorithms
- Adversarial review prompting strategies
- Federated learning aggregation methods

---

## Environment Variables

```
# Factory Database
DATABASE_URL=postgresql+asyncpg://forge:forge@localhost:5432/forge
REDIS_URL=redis://localhost:6379/0

# LLM APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Observability
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com

# Integrations
TAVILY_API_KEY=tvly-...
COMPOSIO_API_KEY=...
CLERK_SECRET_KEY=sk_...
INFISICAL_CLIENT_ID=...
INFISICAL_CLIENT_SECRET=...

# Object Storage
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=forge-packages

# Factory Config
ENVIRONMENT=development
LOG_LEVEL=INFO
HUMAN_REVIEW_REQUIRED=true
MAX_GENERATION_ITERATIONS=5
EVALUATOR_TIMEOUT_SECONDS=600
```

---

## Common Commands

```bash
docker-compose up -d                    # Start local services
uvicorn factory.main:app --reload       # Run factory API
celery -A factory.workers.celery_app worker --loglevel=info  # Pipeline workers
alembic upgrade head                    # Migrations
pytest tests/ -v                        # All tests
pytest tests/integration/ -v            # Full pipeline test
```

---

## Decision Log

Record every significant decision in `DECISIONS.md` with: date, decision, context, alternatives, rationale. Paste relevant entries as context in new Claude Code sessions.

---
Launch Configuration — Resolved Decisions
These decisions define the quality bar, feature completeness, and scope of the V1 launch.
Q1: First Launch Customer
Answer: Internal first. Cognisia uses its own Forge employee to validate before selling to external clients. The first employee operates inside Cognisia, proving the product works before it touches client data. This sets the quality bar: good enough for Cognisia to rely on, which means good enough to sell.
Q2: Deployment Formats at Launch
Answer: All three. Web app (hosted by Cognisia), Electron desktop app (.dmg/.exe/.AppImage), and Docker server deployment. The employee IS the app — all three formats must work at launch. The factory's Deployer produces all three from the same built package.
Q3: Frontend App at Launch
Answer: Full app ships at launch. The conversation UI + sidebar (inbox, activity, documents, memory, settings, updates, metrics) must be complete and production-quality. The app is the product. Without it, there is no product. Backend API alone is not a launch artifact.
Q4: Multi-Tenant Support
Answer: Full multi-tenant production. Multiple clients on shared Cognisia infrastructure AND deployable to client infrastructure. Every database query includes tenant_id. Every vector search is tenant-scoped. Every memory retrieval verifies ownership. Automated cross-tenant access tests run in CI/CD and MUST fail. This is non-negotiable for a product handling client data in regulated industries.
Q5: Auth Model
Answer: Clerk. Already in our stack. Enforced at launch for both the factory portal and employee apps. Clerk handles user authentication, session management, and organization-level access control.
Q6: Data Persistence
Answer: Full persistence from day one. Conversations, approvals, operational memory, knowledge base, and audit trails ALL persisted in Postgres. No in-memory shortcuts. The audit trail is append-only and hash-chained from day one. This is a hard requirement for compliance, litigation defense, and client trust.
Q7: Mandatory Integrations at Launch
Answer: Email (Gmail) + Slack/Teams + Calendar — mandatory and production-ready. CRM (HubSpot/Salesforce), file storage (S3/GDrive), web search (Tavily), and document ingestion (Unstructured) are available but can use mocked/demo fixtures for V1 if needed. The three mandatory integrations must work reliably with real accounts via Composio.
Q8: Placeholder Modules
Answer: Core modules must be production-complete. All Category 1-5 components listed in V1 scope must be fully functional, tested, and reliable. Only explicitly Phase 2+ modules are stubs: growth_engine, computer_use, workforce layer. Everything else is production code, not placeholders.
Q9: Employee Type Support
Answer: Factory supports arbitrary employee types from day one. The Architect, Builder, Evaluator, and Deployer are NOT hardcoded for legal intake. The legal intake agent is the first test of a general-purpose factory. The factory must be able to produce a fundamentally different employee type (e.g., accounting, research operations) by changing the requirements spec — without modifying factory code. This means: universal pipeline stages, configurable component selection, domain-agnostic graph assembly, and parameterized test suites.
Q10: Generator Capability
Answer: Generator must produce runnable custom code. When the Architect identifies a gap the Component Library doesn't cover, the Generator writes real, functional Python modules that implement the standard component interfaces. Stub generation is not acceptable — the "arbitrary employee types" commitment requires the Generator to actually produce domain-specific logic. Self-correcting loop with Evaluator feedback, max 5 iterations. Human review on all generated code in Phase 1.
Q11: Launch-Ready Definition
Answer: Production-grade. Security enforced (Clerk auth, input protection, tenant isolation). Compliance architecture in place (immutable audit trail, explainability records, Tool Broker permission enforcement). Reliability guaranteed (error handling, graceful degradation, monitoring with alerts). This does NOT mean SOC 2 certified at launch — it means the architecture is designed for certification and could pass an audit of the technical controls.
Q12: Compliance Claims at Launch
Answer: "SOC 2-ready architecture." No formal certification at launch (requires 3-6 months and $20-50K). The architecture is designed for compliance: immutable audit trail, tenant isolation, access controls, encryption at rest and in transit, credential management via Infisical, policy enforcement via OPA. Marketing claim: "Built for SOC 2. Certification in progress." No HIPAA, FedRAMP, or CMMC claims until formally certified.
Q13: Monitoring Scope
Answer: Active monitoring with restart/recovery/alerting. Not just passive dashboards. The Monitor detects employee failures, triggers restart attempts, sends alerts to the Cognisia operations team (and optionally to the client), tracks performance degradation, and detects behavioral drift. Health check endpoints on every deployed employee. Integrated with the factory's alerting system.
Q14: Release Gates (Hard Non-Negotiables)
Every gate must pass before V1 ships:

Test suite passes: Functional, security, behavioral, hallucination, compliance tests — all green
All three packaging formats work: Web app deploys and serves, Electron installer produces working .dmg/.exe/.AppImage, Docker Compose runs successfully
Clerk auth enforced: No unauthenticated access to factory portal or employee app
Full persistence verified: Conversations, memory, audit all writing to and reading from Postgres correctly
UI complete: Conversation view + all 7 sidebar sections functional and polished
Real integrations working: Email (Gmail), Slack, and Calendar connected and processing real data via Composio
Multi-tenant isolation verified: Automated cross-tenant access tests run and FAIL (proving isolation works)
Internal pilot successful: Cognisia has used its own Forge employee for at least 2 weeks with no critical failures
Identity architecture working: All 6 layers assembling correctly, behavior change mechanisms functional
Generator produces runnable code: At least one custom module generated, tested, and deployed successfully
