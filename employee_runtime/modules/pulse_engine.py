"""Autonomous daily-loop engine for hosted employees."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from employee_runtime.core.engine import EmployeeEngine
from employee_runtime.core.tool_broker import ToolBroker
from employee_runtime.modules.behavior_manager import BehaviorManager


class DailyLoopRequest(BaseModel):
    conversation_id: str = "default"
    max_items: int = 5
    current_time: str = ""


class DailyLoopPhase(BaseModel):
    name: str
    started_at: str
    completed_at: str
    notes: list[str] = Field(default_factory=list)
    metrics: dict[str, int] = Field(default_factory=dict)


class DailyLoopReport(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    employee_id: str
    workflow: str
    started_at: str
    completed_at: str = ""
    phases: list[DailyLoopPhase] = Field(default_factory=list)
    metrics: dict[str, int] = Field(default_factory=dict)
    outcomes: list[str] = Field(default_factory=list)
    processed_items: list[dict[str, Any]] = Field(default_factory=list)


class PulseEngine:
    """Runs the employee's overnight review, morning briefing, active hours, and wind-down."""

    def __init__(
        self,
        employee_id: str,
        workflow: str,
        engine: EmployeeEngine,
        tool_broker: ToolBroker | None,
        components: dict[str, Any],
        config: dict[str, Any],
        add_message: Any,
        metrics_provider: Any,
        behavior_manager: BehaviorManager | None = None,
    ) -> None:
        self._employee_id = employee_id
        self._workflow = workflow
        self._engine = engine
        self._tool_broker = tool_broker
        self._components = components
        self._config = config
        self._add_message = add_message
        self._metrics_provider = metrics_provider
        self._behavior_manager = behavior_manager

    async def run_daily_loop(self, request: DailyLoopRequest) -> DailyLoopReport:
        current_time = self._resolve_current_time(request.current_time)
        report = DailyLoopReport(
            employee_id=self._employee_id,
            workflow=self._workflow,
            started_at=datetime.now(UTC).isoformat(),
        )

        overnight = await self._overnight_review(report)
        report.phases.append(overnight)

        morning = await self._morning_briefing(report, request.conversation_id, current_time)
        report.phases.append(morning)

        active = await self._active_hours(report, request, current_time)
        report.phases.append(active)

        wind_down = await self._wind_down(report, request.conversation_id, current_time)
        report.phases.append(wind_down)

        report.completed_at = datetime.now(UTC).isoformat()
        await self._persist_report(report)
        return report

    async def _overnight_review(self, report: DailyLoopReport) -> DailyLoopPhase:
        phase = DailyLoopPhase(
            name="overnight_review",
            started_at=datetime.now(UTC).isoformat(),
            completed_at="",
        )
        inbox_messages = await self._check_inbox()
        unread = [message for message in inbox_messages if not message.get("read")]
        phase.metrics = {
            "inbox_total": len(inbox_messages),
            "inbox_unread": len(unread),
        }
        if unread:
            phase.notes.append(f"Queued {len(unread)} unread inbox items for active-hours processing.")
        else:
            phase.notes.append("No unread inbox items were found.")
        report.metrics["inbox_total"] = len(inbox_messages)
        report.metrics["inbox_unread"] = len(unread)
        phase.completed_at = datetime.now(UTC).isoformat()
        return phase

    async def _morning_briefing(
        self,
        report: DailyLoopReport,
        conversation_id: str,
        current_time: datetime,
    ) -> DailyLoopPhase:
        phase = DailyLoopPhase(
            name="morning_briefing",
            started_at=datetime.now(UTC).isoformat(),
            completed_at="",
        )
        metrics = await self._metrics_provider()
        content = (
            f"Morning briefing from {self._config['employee_name']}: "
            f"{report.metrics.get('inbox_unread', 0)} unread items, "
            f"{metrics.get('tasks_total', 0)} completed tasks on record, "
            f"average confidence {metrics.get('avg_confidence', 0.0)}."
        )
        sent = await self._notify_supervisor("Morning briefing", content, urgency="important", current_time=current_time)
        await self._add_message(conversation_id, "system", content, "status_update", {"briefing": True})
        phase.metrics = {"briefings_sent": 1 if sent else 0}
        phase.notes.append(
            "Supervisor briefing sent through available channels."
            if sent
            else "Supervisor briefing suppressed by behavior rules."
        )
        report.metrics["briefings_sent"] = 1 if sent else 0
        phase.completed_at = datetime.now(UTC).isoformat()
        return phase

    async def _active_hours(
        self,
        report: DailyLoopReport,
        request: DailyLoopRequest,
        current_time: datetime,
    ) -> DailyLoopPhase:
        phase = DailyLoopPhase(
            name="active_hours",
            started_at=datetime.now(UTC).isoformat(),
            completed_at="",
        )
        inbox_messages = [message for message in await self._check_inbox() if not message.get("read")][: request.max_items]
        tasks_processed = 0
        calendar_events_created = 0
        crm_updates = 0
        outbound_responses = 0
        supervisor_escalations = 0
        suppressed_notifications = 0

        for message in inbox_messages:
            body = str(message.get("body") or message.get("content") or "")
            sender = str(message.get("from") or message.get("sender") or "")
            subject = str(message.get("subject") or "Inbox task")
            result = await self._engine.process_task(
                body,
                input_type="email",
                metadata={"sender": sender, "subject": subject, "source": "autonomous_daily_loop"},
                conversation_id=request.conversation_id,
            )
            tasks_processed += 1
            card = self._result_card(result)
            schedule_updates = [str(item) for item in card.get("schedule_updates", [])]
            for update in schedule_updates:
                await self._maybe_create_calendar_event(subject, update, sender)
                calendar_events_created += 1

            if sender:
                await self._maybe_upsert_crm_record(sender, subject, card)
                crm_updates += 1

            if result.get("requires_human_approval"):
                supervisor_escalations += 1
                await self._notify_supervisor(
                    f"Approval needed: {subject}",
                    str(card.get("executive_summary") or card.get("title") or "Approval required."),
                    urgency="urgent",
                    current_time=current_time,
                )
                response_delivery = "escalated"
            else:
                if await self._maybe_send_response(sender, subject, card, current_time=current_time):
                    outbound_responses += 1
                    response_delivery = "sent"
                else:
                    suppressed_notifications += 1
                    response_delivery = "suppressed"

            await self._mark_read(message)
            report.processed_items.append(
                {
                    "message_id": str(message.get("id", "")),
                    "subject": subject,
                    "sender": sender,
                    "schedule_updates": schedule_updates,
                    "requires_human_approval": bool(result.get("requires_human_approval")),
                    "response_delivery": response_delivery,
                }
            )

        phase.metrics = {
            "tasks_processed": tasks_processed,
            "calendar_events_created": calendar_events_created,
            "crm_updates": crm_updates,
            "outbound_responses": outbound_responses,
            "supervisor_escalations": supervisor_escalations,
            "suppressed_notifications": suppressed_notifications,
        }
        report.metrics.update(phase.metrics)
        phase.notes.append(f"Processed {tasks_processed} inbox item(s) during active hours.")
        phase.completed_at = datetime.now(UTC).isoformat()
        return phase

    async def _wind_down(
        self,
        report: DailyLoopReport,
        conversation_id: str,
        current_time: datetime,
    ) -> DailyLoopPhase:
        phase = DailyLoopPhase(
            name="wind_down",
            started_at=datetime.now(UTC).isoformat(),
            completed_at="",
        )
        summary = (
            f"Wind-down summary: processed {report.metrics.get('tasks_processed', 0)} tasks, "
            f"created {report.metrics.get('calendar_events_created', 0)} calendar events, "
            f"updated CRM {report.metrics.get('crm_updates', 0)} time(s), "
            f"sent {report.metrics.get('outbound_responses', 0)} direct responses."
        )
        sent = await self._notify_supervisor("End of day summary", summary, urgency="normal", current_time=current_time)
        await self._add_message(conversation_id, "system", summary, "status_update", {"wind_down": True})
        phase.metrics = {"wind_down_reports_sent": 1 if sent else 0}
        report.metrics["wind_down_reports_sent"] = 1 if sent else 0
        if not sent:
            report.metrics["suppressed_notifications"] = report.metrics.get("suppressed_notifications", 0) + 1
            phase.notes.append("Wind-down summary suppressed by behavior rules.")
        report.outcomes.append(summary)
        phase.completed_at = datetime.now(UTC).isoformat()
        return phase

    async def _notify_supervisor(
        self,
        subject: str,
        body: str,
        *,
        urgency: str,
        current_time: datetime,
    ) -> bool:
        if self._tool_broker is None:
            return False
        supervisor_email = str(self._config.get("supervisor_email", "supervisor@example.com"))
        email_allowed = "email_tool" in self._config.get("tool_permissions", []) and not await self._should_suppress(
            channel="email",
            urgency=urgency,
            current_time=current_time,
        )
        messaging_allowed = "messaging_tool" in self._config.get("tool_permissions", []) and not await self._should_suppress(
            channel="messaging",
            urgency=urgency,
            current_time=current_time,
        )
        if not email_allowed and not messaging_allowed:
            return False
        if email_allowed:
            await self._tool_broker.execute(
                "email_tool",
                "send",
                to=supervisor_email,
                subject=subject,
                body=body,
                org_id=str(self._config["org_id"]),
            )
        if messaging_allowed:
            await self._tool_broker.execute(
                "messaging_tool",
                "send",
                to=supervisor_email,
                channel="slack",
                body=body,
                org_id=str(self._config["org_id"]),
            )
        return True

    async def _check_inbox(self) -> list[dict[str, Any]]:
        if self._tool_broker is None or "email_tool" not in self._config.get("tool_permissions", []):
            return []
        result = await self._tool_broker.execute(
            "email_tool",
            "check_inbox",
            criteria="",
            org_id=str(self._config["org_id"]),
        )
        messages = result.data.get("messages", [])
        return [message for message in messages if isinstance(message, dict)]

    async def _mark_read(self, message: dict[str, Any]) -> None:
        if self._tool_broker is None or "email_tool" not in self._config.get("tool_permissions", []):
            return
        await self._tool_broker.execute(
            "email_tool",
            "mark_read",
            message_id=str(message.get("id", "")),
            org_id=str(self._config["org_id"]),
        )

    async def _maybe_create_calendar_event(self, subject: str, update: str, sender: str) -> None:
        if self._tool_broker is None or "calendar_tool" not in self._config.get("tool_permissions", []):
            return
        await self._tool_broker.execute(
            "calendar_tool",
            "create_event",
            title=f"{subject}: {update}",
            time=update,
            attendees=[sender] if sender else [],
            org_id=str(self._config["org_id"]),
        )

    async def _maybe_upsert_crm_record(self, sender: str, subject: str, card: dict[str, Any]) -> None:
        if self._tool_broker is None or "crm_tool" not in self._config.get("tool_permissions", []):
            return
        await self._tool_broker.execute(
            "crm_tool",
            "upsert_contact",
            email=sender,
            name=sender.split("@", 1)[0] if "@" in sender else sender,
            latest_subject=subject,
            latest_summary=str(card.get("executive_summary", "")),
            org_id=str(self._config["org_id"]),
        )

    async def _maybe_send_response(
        self,
        sender: str,
        subject: str,
        card: dict[str, Any],
        *,
        current_time: datetime,
    ) -> bool:
        if not sender or self._tool_broker is None or "email_tool" not in self._config.get("tool_permissions", []):
            return False
        if await self._should_suppress(channel="email", urgency="normal", current_time=current_time):
            return False
        body = str(card.get("drafted_response") or card.get("executive_summary") or card.get("title") or "")
        await self._tool_broker.execute(
            "email_tool",
            "send",
            to=sender,
            subject=f"Re: {subject}",
            body=body,
            org_id=str(self._config["org_id"]),
        )
        return True

    async def _persist_report(self, report: DailyLoopReport) -> None:
        operational_memory = self._components.get("operational_memory")
        audit_system = self._components.get("audit_system")
        payload = report.model_dump(mode="json")
        if operational_memory is not None:
            await operational_memory.store(f"daily_loop:{report.run_id}", payload, "daily_loop")
            await operational_memory.store("daily_loop:latest", payload, "daily_loop")
        if audit_system is not None:
            await audit_system.log_event(
                employee_id=self._employee_id,
                org_id=str(self._config["org_id"]),
                event_type="daily_loop_completed",
                details={
                    "run_id": report.run_id,
                    "workflow": report.workflow,
                    "metrics": report.metrics,
                },
            )

    def _result_card(self, result: dict[str, Any]) -> dict[str, Any]:
        result_card = result.get("result_card", {})
        if isinstance(result_card, dict) and result_card:
            return result_card
        brief = result.get("brief", {})
        return brief if isinstance(brief, dict) else {}

    async def _should_suppress(
        self,
        *,
        channel: str,
        urgency: str,
        current_time: datetime,
    ) -> bool:
        if self._behavior_manager is None:
            return False
        resolution = await self._behavior_manager.resolve_quiet_hours(
            urgency=urgency,
            channel=channel,
            current_time=current_time,
        )
        return bool(resolution.applies and resolution.suppress_non_urgent)

    def _resolve_current_time(self, value: str) -> datetime:
        if value:
            return datetime.fromisoformat(value)
        return datetime.now(UTC)
