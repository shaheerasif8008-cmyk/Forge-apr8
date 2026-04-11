"""Standard employee API — every deployed employee exposes this FastAPI interface."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

import component_library.data.context_assembler  # noqa: F401
import component_library.data.operational_memory  # noqa: F401
import component_library.data.org_context  # noqa: F401
import component_library.data.working_memory  # noqa: F401
import component_library.quality.audit_system  # noqa: F401
import component_library.quality.confidence_scorer  # noqa: F401
import component_library.quality.input_protection  # noqa: F401
import component_library.quality.verification_layer  # noqa: F401
import component_library.tools.email_tool  # noqa: F401
import component_library.work.document_analyzer  # noqa: F401
import component_library.work.draft_generator  # noqa: F401
import component_library.work.text_processor  # noqa: F401
from component_library.component_factory import create_components
from employee_runtime.core.engine import EmployeeEngine
from employee_runtime.core.tool_broker import ToolBroker


WELCOME_MESSAGE = """Hi Sarah, I'm Arthur — your legal intake associate.

I've been configured for Cartwright & Associates. I know your practice areas are
commercial litigation, employment law, and real estate.

Here's what I can do:
• Process intake emails — paste or type an email and I'll extract key information,
  check for conflicts, and produce a structured brief
• Qualify prospects — I'll assess whether a matter fits your firm's criteria
  and recommend next steps
• Morning briefings — I'll summarize activity and flag items needing your attention

You can paste an intake email here, or ask me anything. What would you like to start with?"""


class TaskRequest(BaseModel):
    input: str
    context: dict[str, object] = Field(default_factory=dict)
    conversation_id: str = ""


class TaskResponse(BaseModel):
    task_id: str
    status: str
    output: str = ""
    brief: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    decision: str
    note: str = ""


class SettingsPayload(BaseModel):
    values: dict[str, Any]


class EmployeeRuntimeService:
    def __init__(self, employee_id: str, config: dict[str, Any]) -> None:
        self.employee_id = employee_id
        self.config = config
        self.components: dict[str, Any] = {}
        self.engine: EmployeeEngine | None = None
        self.tool_broker: ToolBroker | None = None
        self.tasks: dict[str, dict[str, Any]] = {}
        self.conversations: dict[str, dict[str, Any]] = {}
        self.messages: dict[str, list[dict[str, Any]]] = {}
        self.approvals: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        if self.engine is not None:
            return
        component_ids = [
            "text_processor",
            "document_analyzer",
            "draft_generator",
            "operational_memory",
            "working_memory",
            "context_assembler",
            "org_context",
            "confidence_scorer",
            "audit_system",
            "input_protection",
            "verification_layer",
            "email_tool",
        ]
        component_config = {
            "text_processor": {},
            "document_analyzer": {"practice_areas": self.config.get("practice_areas", [])},
            "draft_generator": {"default_attorney": self.config.get("default_attorney", "Review Attorney")},
            "operational_memory": {
                "org_id": self.config["org_id"],
                "employee_id": self.employee_id,
            },
            "working_memory": {
                "org_id": self.config["org_id"],
                "employee_id": self.employee_id,
                "redis_url": self.config.get("redis_url", ""),
            },
            "context_assembler": {
                "operational_memory": None,
                "system_identity": self.config.get("system_identity", ""),
            },
            "org_context": {
                "people": self.config.get("people", []),
                "escalation_chain": self.config.get("escalation_chain", []),
                "firm_info": self.config.get("firm_info", {}),
            },
            "confidence_scorer": {},
            "audit_system": {},
            "input_protection": {},
            "verification_layer": {},
            "email_tool": {"fixtures": self.config.get("email_fixtures", [])},
        }
        self.components = await create_components(component_ids, component_config)
        self.components["context_assembler"]._operational_memory = self.components["operational_memory"]
        self.tool_broker = ToolBroker(
            employee_id=self.employee_id,
            allowed_tools=["email_tool"],
            tools={"email_tool": self.components["email_tool"]},
            audit_logger=self.components["audit_system"].log_event,
        )
        self.engine = EmployeeEngine(
            "legal_intake",
            self.components,
            {"employee_id": self.employee_id, "org_id": self.config["org_id"]},
        )

    def _default_conversation_id(self) -> str:
        return self.config.get("default_conversation_id", "default")

    async def ensure_conversation(self, conversation_id: str = "") -> str:
        conv_id = conversation_id or self._default_conversation_id()
        if conv_id not in self.conversations:
            self.conversations[conv_id] = {
                "id": conv_id,
                "employee_id": self.employee_id,
                "org_id": str(self.config["org_id"]),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            self.messages[conv_id] = []
        return conv_id

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        message = {
            "id": f"{conversation_id}:{len(self.messages[conversation_id]) + 1}",
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "message_type": message_type,
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.messages[conversation_id].append(message)
        return message

    async def history(self, conversation_id: str) -> list[dict[str, Any]]:
        conv_id = await self.ensure_conversation(conversation_id)
        history = list(self.messages[conv_id])
        if not history:
            history.append(
                await self.add_message(conv_id, "assistant", WELCOME_MESSAGE, "text", {"first_run": True})
            )
        return history

    async def submit_task(self, request: TaskRequest) -> dict[str, Any]:
        if self.engine is None:
            raise RuntimeError("Employee runtime service is not initialized.")
        conv_id = await self.ensure_conversation(request.conversation_id)
        await self.add_message(conv_id, "user", request.input, "text", dict(request.context))
        result = await self.engine.process_task(
            request.input,
            input_type=str(request.context.get("input_type", "email")),
            metadata=request.context,
            conversation_id=conv_id,
        )
        task_id = result["task_id"]
        self.tasks[task_id] = result
        await self.add_message(conv_id, "assistant", "Intake brief ready for review.", "status_update", {"task_id": task_id})
        approval_message = await self.add_message(
            conv_id,
            "assistant",
            result.get("brief", {}).get("executive_summary", ""),
            "approval_request",
            {
                "task_id": task_id,
                "status": "pending",
                "brief": result.get("brief", {}),
                "decision": "",
            },
        )
        self.approvals[approval_message["id"]] = approval_message
        return result

    async def task_status(self, task_id: str) -> dict[str, Any]:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        return self.tasks[task_id]

    async def task_brief(self, task_id: str) -> dict[str, Any]:
        task = await self.task_status(task_id)
        return task.get("brief", {})

    async def list_approvals(self) -> list[dict[str, Any]]:
        return [approval for approval in self.approvals.values() if approval["metadata"].get("status") == "pending"]

    async def decide_approval(self, message_id: str, decision: str, note: str) -> dict[str, Any]:
        if message_id not in self.approvals:
            raise KeyError(message_id)
        approval = self.approvals[message_id]
        approval["metadata"]["status"] = decision
        approval["metadata"]["decision"] = decision
        approval["metadata"]["note"] = note
        await self.components["audit_system"].log_event(
            employee_id=self.employee_id,
            org_id=str(self.config["org_id"]),
            event_type="approval_decided",
            details={"message_id": message_id, "decision": decision, "note": note},
        )
        return approval

    async def get_settings(self) -> dict[str, Any]:
        prefs = await self.components["operational_memory"].list_by_category("preference")
        return {
            pref["key"].removeprefix("pref:"): pref["value"].get("value", pref["value"])
            for pref in prefs
        }

    async def put_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        for key, value in values.items():
            await self.components["operational_memory"].store(f"pref:{key}", {"value": value}, "preference")
        return await self.get_settings()

    async def activity(self) -> list[dict[str, Any]]:
        return await self.components["audit_system"].get_trail(self.employee_id)

    async def metrics(self) -> dict[str, Any]:
        activity = await self.activity()
        completed = [event for event in activity if event["event_type"] == "task_completed"]
        outputs = [event for event in activity if event["event_type"] == "output_produced"]
        approvals = [event for event in activity if event["event_type"] == "approval_decided"]
        confidence_values = [
            event["details"].get("confidence", 0.0)
            for event in outputs
            if isinstance(event.get("details"), dict) and "confidence" in event["details"]
        ]
        return {
            "tasks_total": len(completed),
            "avg_confidence": round(sum(confidence_values) / len(confidence_values), 2) if confidence_values else 0.0,
            "approval_mix": {
                decision: len([event for event in approvals if event["details"].get("decision") == decision])
                for decision in ("approve", "decline", "modify")
            },
            "avg_duration_seconds": 0.0,
        }

    async def send_morning_briefing(self, conversation_id: str = "") -> dict[str, Any]:
        conv_id = await self.ensure_conversation(conversation_id)
        metrics = await self.metrics()
        content = (
            f"Morning briefing: {metrics['tasks_total']} tasks completed so far. "
            f"Average confidence {metrics['avg_confidence']}."
        )
        message = await self.add_message(conv_id, "system", content, "status_update", {"briefing": True})
        if self.tool_broker is not None:
            await self.tool_broker.execute(
                "email_tool",
                "send",
                to=self.config.get("supervisor_email", "supervisor@example.com"),
                subject="Morning briefing",
                body=content,
                org_id=str(self.config["org_id"]),
            )
        return message


def create_employee_app(employee_id: str, config: dict[str, Any] | None = None) -> FastAPI:
    """Create the standard FastAPI app for a deployed employee."""
    runtime_config = {
        "org_id": (config or {}).get("org_id", "demo-org"),
        "practice_areas": (config or {}).get(
            "practice_areas",
            ["personal injury", "employment", "commercial dispute", "real estate"],
        ),
        "default_attorney": (config or {}).get("default_attorney", "Arthur Review"),
        "supervisor_email": (config or {}).get("supervisor_email", "partner@cartwright.example"),
        "system_identity": (config or {}).get(
            "system_identity",
            "You are Arthur, a legal intake associate for Cartwright & Associates.",
        ),
        "people": (config or {}).get(
            "people",
            [
                {
                    "name": "Sarah Cartwright",
                    "role": "Managing Partner",
                    "email": "partner@cartwright.example",
                    "relationship": "supervisor",
                }
            ],
        ),
        "escalation_chain": (config or {}).get("escalation_chain", ["Sarah Cartwright"]),
        "firm_info": (config or {}).get(
            "firm_info",
            {"name": "Cartwright & Associates", "practice_areas": ["commercial litigation", "employment law", "real estate"]},
        ),
        "redis_url": (config or {}).get("redis_url", ""),
        "email_fixtures": (config or {}).get("email_fixtures", []),
    }
    service = EmployeeRuntimeService(employee_id, runtime_config)

    async def ensure_ready() -> None:
        await service.initialize()
        await service.ensure_conversation()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await ensure_ready()
        yield

    app = FastAPI(title=f"Employee API — {employee_id}", version="1.0.0", lifespan=lifespan)

    @app.get("/health")
    async def health() -> dict[str, str]:
        await ensure_ready()
        return {"status": "ok", "employee_id": employee_id}

    @app.post("/api/v1/chat")
    async def chat(request: TaskRequest) -> dict[str, Any]:
        await ensure_ready()
        result = await service.submit_task(request)
        return {"task_id": result["task_id"], "message_type": "brief_card", "data": result.get("brief", {})}

    @app.get("/api/v1/chat/history")
    async def chat_history(conversation_id: str = "") -> dict[str, Any]:
        await ensure_ready()
        return {"conversation_id": conversation_id or service._default_conversation_id(), "messages": await service.history(conversation_id)}

    @app.post("/api/v1/tasks", response_model=TaskResponse)
    async def submit_task(request: TaskRequest) -> TaskResponse:
        await ensure_ready()
        result = await service.submit_task(request)
        return TaskResponse(
            task_id=result["task_id"],
            status="completed",
            output=result.get("qualification_reasoning", ""),
            brief=result.get("brief", {}),
        )

    @app.get("/api/v1/tasks/{task_id}")
    async def get_task(task_id: str) -> dict[str, Any]:
        await ensure_ready()
        try:
            return await service.task_status(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task_not_found") from exc

    @app.get("/api/v1/tasks/{task_id}/brief")
    async def get_task_brief(task_id: str) -> dict[str, Any]:
        await ensure_ready()
        try:
            return await service.task_brief(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task_not_found") from exc

    @app.get("/api/v1/activity")
    async def get_activity() -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.activity()

    @app.get("/api/v1/approvals")
    async def get_approvals() -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.list_approvals()

    @app.post("/api/v1/approvals/{message_id}/decide")
    async def decide_approval(message_id: str, payload: ApprovalDecision) -> dict[str, Any]:
        await ensure_ready()
        try:
            return await service.decide_approval(message_id, payload.decision, payload.note)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="approval_not_found") from exc

    @app.get("/api/v1/settings")
    async def get_settings() -> dict[str, Any]:
        await ensure_ready()
        return await service.get_settings()

    @app.put("/api/v1/settings")
    async def update_settings(payload: SettingsPayload) -> dict[str, Any]:
        await ensure_ready()
        return await service.put_settings(payload.values)

    @app.get("/api/v1/metrics")
    async def get_metrics() -> dict[str, Any]:
        await ensure_ready()
        return await service.metrics()

    @app.websocket("/api/v1/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await ensure_ready()
        await websocket.accept()
        try:
            while True:
                payload = await websocket.receive_json()
                if payload.get("type") != "chat_message":
                    await websocket.send_json({"type": "error", "message": "unsupported_message"})
                    continue
                conversation_id = await service.ensure_conversation(payload.get("conversation_id", ""))
                await service.add_message(conversation_id, "user", payload["content"], "text", {})
                async for event in service.engine.process_task_streaming(
                    payload["content"],
                    conversation_id=conversation_id,
                ):
                    if event["type"] == "status":
                        await websocket.send_json({"type": "status", "node": event["node"], "status": event["status"]})
                    elif event["type"] == "complete":
                        state = event["state"]
                        task_id = state["task_id"]
                        service.tasks[task_id] = state
                        approval_message = await service.add_message(
                            conversation_id,
                            "assistant",
                            state.get("brief", {}).get("executive_summary", ""),
                            "approval_request",
                            {"task_id": task_id, "status": "pending", "brief": state.get("brief", {})},
                        )
                        service.approvals[approval_message["id"]] = approval_message
                        summary = state.get("brief", {}).get("executive_summary", "")
                        for token in summary.split():
                            await websocket.send_json({"type": "token", "content": f"{token} "})
                        await websocket.send_json({"type": "complete", "message_type": "brief_card", "data": state.get("brief", {})})
        except WebSocketDisconnect:
            return

    return app
