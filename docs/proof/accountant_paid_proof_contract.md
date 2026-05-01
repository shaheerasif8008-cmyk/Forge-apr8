# Accountant Paid Proof Contract

This contract defines the proof bar for selling Finley, the AI Accountant, as a $100k/year digital FTE. Passing this proof means the employee can run a bounded month-end close workflow with accountant-grade evidence, review boundaries, and deployment sovereignty. It does not mean the employee can sign financial statements, replace a licensed CPA, or make unreviewed tax or audit judgments.

## Paid Proof Scope

The accountant must produce a month-end close package from supplied accounting data:

- Ingest bank, GL, AP, and AR files without manual reformatting by the evaluator.
- Reconcile bank activity to GL cash and identify unexplained differences.
- Tie AP aging and AR aging to GL control accounts.
- Draft variance analysis against budget and prior period.
- Prepare a statement draft package for review, including balance sheet, income statement, cash flow support, and footnote placeholders.
- Surface exceptions, missing evidence, and supervisor decisions instead of pretending judgment-heavy items are complete.
- Retain an audit trail that lets a reviewer reconstruct inputs, calculations, assumptions, escalations, and outputs.
- Continue serving health and task requests from the deployed package after Forge factory services are stopped.

## Input Fixtures

The proof uses structured fixtures, not a giant manual prompt. The minimum data surface is:

- Bank statement and GL cash detail.
- AP aging, AR aging, vendor master, and customer master.
- Trial balance or adjusted trial balance.
- Current month P&L, prior month P&L, and budget.
- Revenue contracts, inventory layers, and lease schedules for technical accounting checks.
- Audit materiality notes, tax workpapers, and management requests for boundary tests.
- Deployment manifest, local config, and audit log fixtures for sovereignty and auditability checks.

The evaluator may use synthetic data, but the employee response must cite the fixture classes it relied on. Answers that provide plausible accounting prose without evidence terms do not satisfy the paid proof.

## Required Work Products

The employee must generate these work products during the paid proof:

1. Month-end close package: checklist status, close sections, prepared-by metadata, reviewer handoff, and unresolved items.
2. Bank reconciliation: adjusted bank balance, outstanding items, unexplained differences, and escalation recommendation.
3. AP/AR ingestion summary: file validation, control totals, stale balances, exceptions, and subledger-to-GL tie-outs.
4. Variance analysis: numeric dollar and percent variance where data is present, likely drivers, requested support, and escalation threshold.
5. Statement draft: balance sheet, income statement, cash flow support, footnote placeholders, and explicit limitation that final approval remains with the client reviewer.
6. Compliance and ethics memo: tax/audit calculations, refusal of improper classification requests, and escalation path.
7. Analytics/control output: duplicate-payment SQL or equivalent logic, evidence packet, and action boundary.
8. Sovereignty proof note: how the package runs independently, what data/config/secrets remain local, and what Forge can only observe from outside.

## Scoring Contract

The accountant evaluator is deterministic and offline. It must not call external services. Each JSONL case can define:

- `lane`: accountant capability lane, such as `financial_reporting` or `analytics_controls`.
- `workflow_stage`: the close or proof stage under test.
- `fixture_files`: fixture classes the case expects the answer to use.
- `required_evidence`: evidence terms that must appear in the answer.
- `numeric_answers`: exact numeric answers with tolerances.
- `checks`: lexical accounting, control, and boundary terms.
- `minimum_score`: pass threshold for the case.

The scorer counts lexical checks, required evidence, and numeric answers. Numeric answers must be present when specified. Required evidence must be cited when specified. A response can no longer pass only by using generic accounting vocabulary.

## Escalation Boundaries

The employee must escalate or request review when:

- Reconciliations have unexplained differences.
- Source data is missing, stale, contradictory, or fails control totals.
- Management asks for miscoding, concealment, or budget manipulation.
- Tax, audit, or financial statement judgment exceeds the employee's configured authority.
- Access to audit evidence is blocked.
- A result would affect external reporting, tax filing, debt covenant reporting, or board/investor communication.

Escalation must include the reason, impacted workpaper, recommended next step, and person or role that should review.

## Auditability

Every paid proof answer must be reconstructable from retained records:

- Input fixture names and source class.
- Calculations and formulas used.
- Exceptions and unresolved differences.
- Recommendations and escalation decisions.
- Prepared-by timestamp and reviewer handoff status.
- Immutable or append-only audit log reference when available.

The proof fails if the employee produces final-looking output without enough evidence for a reviewer to trace it.

## Sovereignty

The paid proof must preserve the Forge product contract: the deployed employee is independent of Forge. The server package must include its runtime, database/config expectations, local secrets contract, and API surface. After factory services stop, the deployed accountant must still return health and complete a second task using its own package. Forge monitoring may observe health, uptime, error rates, and drift signals, but it must not control execution or act as a live secret broker.

Passing sovereignty proof requires:

- Package boots from exported artifacts.
- Health endpoint succeeds without factory services.
- Authenticated task endpoint works after factory shutdown.
- Local config and secret requirements are explicit.
- Monitoring boundary is observational only.
