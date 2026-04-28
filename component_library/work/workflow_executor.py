"""workflow_executor work capability component."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.registry import register
from component_library.work.schemas import ExecutiveAssistantInput, ExecutiveAssistantPlan


@register("workflow_executor")
class WorkflowExecutor(WorkCapability):
    config_schema = {
        "auto_actions": {"type": "list", "required": False, "description": "Action names the executor may run without approval.", "default": ["analyze", "draft", "classify"]},
    }
    component_id = "workflow_executor"
    version = "1.0.0"
    _auto_actions: list[str] = ["triage request", "draft response", "prepare follow-up"]

    async def initialize(self, config: dict[str, Any]) -> None:
        self._auto_actions = config.get(
            "auto_actions",
            ["triage request", "draft response", "prepare follow-up"],
        )

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_workflow_executor.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, ExecutiveAssistantInput):
            raise TypeError("WorkflowExecutor expects ExecutiveAssistantInput")
        return self.plan(input_data.request_text)

    def plan(self, request_text: str) -> ExecutiveAssistantPlan:
        lowered = request_text.lower()
        requested_actions = list(self._auto_actions)
        finance_actions: list[str] = []
        finance_metrics: dict[str, float] = {}
        finance_summary = ""
        recognized_intent = False
        if "schedule" in lowered or "meeting" in lowered:
            requested_actions.insert(0, "coordinate calendar")
            recognized_intent = True
        if "client" in lowered or "customer" in lowered:
            requested_actions.append("update crm record")
            recognized_intent = True
        stakeholders = []
        if "sarah" in lowered:
            stakeholders.append("Sarah")
        if "finance" in lowered:
            stakeholders.append("Finance")
        if "follow-up" in lowered or "follow up" in lowered or "respond" in lowered or "reply" in lowered:
            recognized_intent = True
        finance_result = self._finance_actions(request_text)
        if finance_result["actions"]:
            recognized_intent = True
            finance_actions = finance_result["actions"]
            finance_metrics = finance_result["metrics"]
            finance_summary = finance_result["summary"]
            requested_actions = finance_actions + requested_actions
        requires_approval = any(keyword in lowered for keyword in ("approve", "sign", "send to all"))
        if finance_metrics.get("largest_overdue_amount", 0.0) >= 10000:
            requires_approval = True
        novel_trigger = self._novel_trigger(lowered, recognized_intent)
        is_novel_situation = novel_trigger != ""
        novel_options = self._novel_options(request_text) if is_novel_situation else []
        return ExecutiveAssistantPlan(
            summary=(finance_summary or request_text.strip())[:240],
            requested_actions=requested_actions[:5],
            finance_actions=finance_actions[:5],
            finance_summary=finance_summary[:240],
            finance_metrics=finance_metrics,
            stakeholders=stakeholders,
            meeting_topics=["meeting coordination"] if "meeting" in lowered else [],
            deadlines=["high priority"] if "asap" in lowered or "urgent" in lowered else [],
            requires_approval=requires_approval or is_novel_situation,
            rationale="Derived from request intent, timing cues, and stakeholder mentions.",
            is_novel_situation=is_novel_situation,
            novel_options=novel_options,
            recommended_option=novel_options[0]["key"] if novel_options else "",
            guidance_request=(
                "I haven't handled this exact situation before. Here are three approaches with tradeoffs."
                if is_novel_situation
                else ""
            ),
            novel_trigger=novel_trigger,
        )

    def _novel_trigger(self, lowered: str, recognized_intent: bool) -> str:
        explicit_cues = (
            "never handled",
            "never seen",
            "first time",
            "novel",
            "untested",
            "creative option",
            "outside our normal process",
            "outside your domain",
            "something new",
        )
        for cue in explicit_cues:
            if cue in lowered:
                return cue
        if not recognized_intent and len(lowered.split()) >= 8:
            return "unrecognized_request_pattern"
        return ""

    def _novel_options(self, request_text: str) -> list[dict[str, str]]:
        summary = request_text.strip()[:120]
        return [
            {
                "key": "A",
                "label": "Safest",
                "description": f"Pause external action, gather missing facts, and confirm the right process for: {summary}",
            },
            {
                "key": "B",
                "label": "Faster",
                "description": f"Take the most likely next step for: {summary}, but keep the action reversible and reviewable.",
            },
            {
                "key": "C",
                "label": "Creative",
                "description": f"Try a new approach for: {summary}, mark it as untested, and escalate results immediately.",
            },
        ]

    def _finance_actions(self, request_text: str) -> dict[str, Any]:
        lowered = request_text.lower()
        finance_keywords = (
            "invoice",
            "ap ",
            "a/p",
            "ar ",
            "a/r",
            "aging",
            "overdue",
            "payable",
            "receivable",
            "expense",
            "month-end",
            "month end",
            "close",
            "reconcile",
        )
        if not any(keyword in lowered for keyword in finance_keywords):
            return {"actions": [], "metrics": {}, "summary": ""}

        invoice_pattern = re.compile(
            r"\b(?P<invoice>(?:INV|BILL|AR|AP)[-\s]?\d+)\b"
            r"(?:[^$\n\r]*?(?P<days>\d{1,3})\s+days?\s+overdue)?"
            r"[^$\n\r]*?\$(?P<amount>[\d,]+(?:\.\d{1,2})?)",
            re.IGNORECASE,
        )
        matches = list(invoice_pattern.finditer(request_text))
        if not matches:
            return {
                "actions": ["Extract invoice lines and prepare aging follow-up queue"],
                "metrics": {},
                "summary": "Accounting request received; preparing actionable aging and follow-up plan.",
            }

        overdue_rows: list[dict[str, Any]] = []
        for match in matches:
            invoice = match.group("invoice").replace(" ", "").upper()
            days_raw = match.group("days")
            days = int(days_raw) if days_raw else 0
            amount = float(match.group("amount").replace(",", ""))
            overdue_rows.append({"invoice": invoice, "days": days, "amount": amount})

        overdue_rows.sort(key=lambda row: (row["days"], row["amount"]), reverse=True)
        total_overdue = sum(row["amount"] for row in overdue_rows)
        highest = overdue_rows[0]

        actions = [
            (
                f"Send payment follow-up for {row['invoice']} "
                f"(${row['amount']:,.2f}, {row['days']} days overdue)"
            )
            for row in overdue_rows[:3]
        ]
        actions.append("Escalate invoices >= $10,000 or 30+ days overdue for controller review")

        summary = (
            f"AP/AR aging parsed: {len(overdue_rows)} overdue invoices totaling ${total_overdue:,.2f}; "
            f"highest risk is {highest['invoice']} (${highest['amount']:,.2f}, {highest['days']} days overdue)."
        )
        metrics = {
            "overdue_invoice_count": float(len(overdue_rows)),
            "total_overdue_amount": round(total_overdue, 2),
            "largest_overdue_amount": round(highest["amount"], 2),
        }
        return {"actions": actions, "metrics": metrics, "summary": summary}
