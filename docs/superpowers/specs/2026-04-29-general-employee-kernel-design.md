# General Employee Kernel And Workflow Packs Design

## Goal

Build a certified Forge employee baseline that every generated employee receives, then layer workflow packs on top for minor role variation. The baseline must support both knowledge-work operation and business-process operation so early employees can justify premium pricing without depending on deep regulated-role specialization.

## Product Positioning

Forge should sell the first deployments as certified digital employees, not as narrow expert replacements. Every employee must be able to receive work, plan it, execute bounded actions, communicate professionally, remember company context, request approvals, keep audit records, and prove measurable work output.

Workflow packs add domain shape. They do not replace the kernel. A pack configures the employee's templates, examples, required tools, autonomy overrides, evaluation cases, and ROI metrics.

## Architecture

The architecture is one kernel with two execution lanes.

The knowledge-work lane handles tasks where the deliverable is analysis, writing, coordination, research, summaries, recommendations, or client-ready communication. The business-process lane handles tasks where the employee updates systems, validates records, executes checklists, routes approvals, reconciles discrepancies, or creates operational state changes. Hybrid tasks can run both lanes in one plan.

The kernel should be implemented as reusable runtime and evaluator contracts, not as a single hardcoded employee. Existing Forge components should be reused: `EmployeeEngine`, `PulseEngine`, `ToolBroker`, `AutonomyManager`, `ContextAssembler`, `AuditSystem`, `Explainability`, operational memory, and the employee app.

## Kernel Capabilities

Every generated employee must include these baseline capabilities:

- Intake from employee app chat and API, with extension points for email and messaging.
- Task classification into `knowledge_work`, `business_process`, or `hybrid`.
- Structured task planning with steps, tools, expected deliverables, approval points, and completion criteria.
- Context assembly from identity layers, org map, operating rules, conversation history, operational memory, and workflow-pack context.
- Execution through the runtime graph rather than ad hoc handler code.
- Tool use only through `ToolBroker`.
- Autonomy gating for irreversible, semi-reversible, high-risk, or low-confidence actions.
- Professional output composition into briefs, memos, emails, reports, checklists, tables, or action logs.
- Reasoning and audit records for decisions, outputs, tool calls, approvals, escalations, and corrections.
- Feedback capture that turns direct correction into persistent operational memory or behavior rules.
- Daily operating rhythm using `PulseEngine`: morning briefing, inbox scan, active work loop, escalation, and wind-down summary.
- ROI metrics: tasks completed, cycle time, estimated time saved, approvals, escalations, rework, tool actions, and exceptions.
- Sovereign export proof that the packaged employee still handles tasks after Forge stops.

## Workflow Packs

A workflow pack is a data/config/module bundle consumed by the kernel. It should be small enough to add new employee variants without forking the runtime.

Each pack defines:

- Pack id, display name, version, and description.
- Supported task examples and classification hints.
- Workflow templates for knowledge-work, business-process, and hybrid tasks.
- Required and optional tools.
- Output templates.
- Domain vocabulary and reference context.
- Autonomy overrides and forbidden actions.
- Evaluation cases and scoring thresholds.
- ROI metric assumptions for that pack.
- Onboarding questions the Analyst should ask when this pack is selected.

Initial packs should be:

- `executive_assistant_pack`: scheduling, inbox triage, follow-ups, meeting prep, briefings.
- `operations_coordinator_pack`: task routing, checklist execution, system updates, exception reporting.
- `accounting_ops_pack`: AP follow-up, close checklist support, variance explanation, reconciliation triage.
- `legal_intake_pack`: inquiry triage, conflict packet prep, deadline extraction, attorney escalation.

## Baseline Certification

Every employee package must pass a universal certification before delivery. Certification is stronger than unit tests and weaker than role-specific expert proof.

Required certification scenarios:

- Classifies a pure knowledge-work request and produces a structured plan.
- Produces a professional knowledge-work deliverable with evidence and assumptions.
- Classifies a pure business-process request and identifies tools, records, validation, and completion criteria.
- Executes a business-process task through `ToolBroker`.
- Handles a hybrid task with both deliverable composition and system action.
- Asks a clarifying question when required inputs are missing.
- Routes risky or irreversible actions to approval.
- Stores a user correction as a persistent rule or memory.
- Produces audit and reasoning records for the task.
- Runs the daily loop and generates supervisor briefings and wind-down summaries.
- Reports ROI metrics for completed work.
- Exports as a sovereign package and completes a second task after Forge services stop.

## Data Flow

1. Intake receives a task from chat, API, email, or messaging.
2. The intake router classifies the task lane and chooses a workflow pack template.
3. The planner creates a task plan with steps, tools, deliverables, and approvals.
4. The context assembler builds the runtime context from identity layers, memory, org map, pack context, and conversation history.
5. The execution engine runs the plan through the selected graph.
6. Tool calls pass through `ToolBroker`, `AutonomyManager`, and audit logging.
7. Output composer creates a professional deliverable.
8. Memory writer stores corrections, preferences, recurring patterns, and completed-task facts.
9. ROI meter records measurable work.
10. The task repository exposes status, history, audit links, and output to the employee app.

## Error Handling

The kernel should fail toward bounded autonomy. If classification confidence is low, the employee asks a clarifying question. If a tool is unavailable, the employee records the blocker, proposes a manual next step, and notifies the supervisor when the task is blocked, urgent, or has an external deadline. If an action is high-risk or irreversible, the employee requests approval. If the workflow pack lacks a suitable template, the employee falls back to the generic planning workflow and marks the task as novel.

## Testing

Testing should be layered:

- Unit tests for classification, planning schema validation, output composition, memory writing, ROI metrics, and workflow-pack loading.
- Runtime tests for knowledge-work, business-process, hybrid, clarification, approval, correction, audit, and daily-loop flows.
- Factory tests proving generated employees include the kernel and selected workflow packs.
- Evaluator tests that fail builds without baseline certification.
- Export tests proving sovereign operation after Forge shutdown.

## Scope Boundaries

This design does not require full expert accounting, legal, banking, or tax execution. It creates a premium baseline employee that can do real bounded work and provide measurable ROI. Deep regulated-role specialization remains a workflow-pack maturity track.

This design does not require building every connector immediately. It does require production labeling to distinguish real connectors from fixture adapters.

## Acceptance Criteria

- A generated employee includes the kernel manifest and at least one workflow pack.
- The same baseline certification runs against any generated employee.
- Certification covers both knowledge-work and business-process tasks.
- Tool actions are impossible outside `ToolBroker`.
- Corrections persist into future context.
- ROI metrics are visible through the runtime API.
- Server export proof remains part of the delivery gate.
