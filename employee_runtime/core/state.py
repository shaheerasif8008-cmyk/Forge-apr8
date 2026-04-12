"""Shared state model for employee LangGraph workflows."""

from __future__ import annotations

from typing import TypedDict


class EmployeeState(TypedDict, total=False):
    task_id: str
    employee_id: str
    org_id: str
    conversation_id: str
    raw_input: str
    input_type: str
    input_metadata: dict
    sanitization_result: dict
    extracted_data: dict
    analysis: dict
    confidence_report: dict
    verification_result: dict
    qualification_decision: str
    qualification_reasoning: str
    brief: dict
    result_card: dict
    response_summary: str
    workflow_output: dict
    novel_options: list
    correction_record: dict
    delivery_method: str
    delivery_status: str
    errors: list
    audit_event_ids: list
    requires_human_approval: bool
    escalation_reason: str
    started_at: str
    completed_at: str
