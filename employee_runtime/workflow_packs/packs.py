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
