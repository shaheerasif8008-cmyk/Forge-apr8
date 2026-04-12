"""Standard employee API — every deployed employee exposes this FastAPI interface."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

import component_library.data.context_assembler  # noqa: F401
import component_library.data.operational_memory  # noqa: F401
import component_library.data.org_context  # noqa: F401
import component_library.data.working_memory  # noqa: F401
import component_library.quality.audit_system  # noqa: F401
import component_library.quality.autonomy_manager  # noqa: F401
import component_library.quality.confidence_scorer  # noqa: F401
import component_library.quality.input_protection  # noqa: F401
import component_library.quality.verification_layer  # noqa: F401
import component_library.tools.calendar_tool  # noqa: F401
import component_library.tools.crm_tool  # noqa: F401
import component_library.tools.email_tool  # noqa: F401
import component_library.tools.messaging_tool  # noqa: F401
import component_library.work.communication_manager  # noqa: F401
import component_library.work.document_analyzer  # noqa: F401
import component_library.work.draft_generator  # noqa: F401
import component_library.work.scheduler_manager  # noqa: F401
import component_library.work.text_processor  # noqa: F401
import component_library.work.workflow_executor  # noqa: F401
from component_library.component_factory import create_components
from employee_runtime.core.engine import EmployeeEngine
from employee_runtime.core.tool_broker import ToolBroker


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
        self.config = _normalize_runtime_config(employee_id, config)
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

        component_ids = [component["id"] for component in self.config["components"]]
        component_config = self._component_config()
        self.components = await create_components(component_ids, component_config)

        if "context_assembler" in self.components and "operational_memory" in self.components:
            self.components["context_assembler"]._operational_memory = self.components["operational_memory"]

        tool_ids = [component_id for component_id in component_ids if component_id.endswith("_tool")]
        tools = {tool_id: self.components[tool_id] for tool_id in tool_ids if tool_id in self.components}
        self.tool_broker = ToolBroker(
            employee_id=self.employee_id,
            allowed_tools=self.config["tool_permissions"],
            tools=tools,
            audit_logger=self.components.get("audit_system", None).log_event if self.components.get("audit_system") else None,
        )
        self.engine = EmployeeEngine(
            self.config["workflow"],
            self.components,
            {"employee_id": self.employee_id, "org_id": self.config["org_id"]},
        )

    def _component_config(self) -> dict[str, dict[str, Any]]:
        component_config = {component["id"]: dict(component.get("config", {})) for component in self.config["components"]}
        component_config.setdefault("operational_memory", {}).update(
            {"org_id": self.config["org_id"], "employee_id": self.employee_id}
        )
        component_config.setdefault("working_memory", {}).update(
            {
                "org_id": self.config["org_id"],
                "employee_id": self.employee_id,
                "redis_url": self.config.get("redis_url", ""),
            }
        )
        component_config.setdefault("context_assembler", {}).update(
            {
                "operational_memory": None,
                "system_identity": self.config["identity_layers"]["layer_2_role_definition"],
                "identity_layers": self.config["identity_layers"],
            }
        )
        component_config.setdefault("org_context", {}).update(
            {
                "people": self.config["org_map"],
                "escalation_chain": self.config.get("escalation_chain", []),
                "firm_info": self.config.get("firm_info", {}),
            }
        )
        component_config.setdefault("document_analyzer", {}).update(
            {"practice_areas": self.config.get("practice_areas", [])}
        )
        component_config.setdefault("draft_generator", {}).update(
            {"default_attorney": self.config.get("default_attorney", "Forge Review")}
        )
        component_config.setdefault("communication_manager", {}).update(
            {
                "signature": self.config["employee_name"],
                "voice": "clear and action-oriented",
            }
        )
        component_config.setdefault("scheduler_manager", {}).update(
            {"timezone": self.config.get("timezone", "America/New_York")}
        )
        component_config.setdefault("email_tool", {}).update({"fixtures": self.config.get("email_fixtures", [])})
        component_config.setdefault("calendar_tool", {}).update({"fixtures": self.config.get("calendar_fixtures", [])})
        component_config.setdefault("messaging_tool", {}).update({"fixtures": self.config.get("message_fixtures", [])})
        component_config.setdefault("crm_tool", {}).update({"fixtures": self.config.get("crm_fixtures", {})})
        return component_config

    def _default_conversation_id(self) -> str:
        return self.config.get("default_conversation_id", "default")

    async def ensure_conversation(self, conversation_id: str = "") -> str:
        conv_id = conversation_id or self._default_conversation_id()
        if conv_id not in self.conversations:
            self.conversations[conv_id] = {
                "id": conv_id,
                "employee_id": self.employee_id,
                "org_id": str(self.config["org_id"]),
                "created_at": datetime.now(UTC).isoformat(),
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
            "created_at": datetime.now(UTC).isoformat(),
        }
        self.messages[conversation_id].append(message)
        return message

    async def history(self, conversation_id: str) -> list[dict[str, Any]]:
        conv_id = await self.ensure_conversation(conversation_id)
        history = list(self.messages[conv_id])
        if not history:
            history.append(await self.add_message(conv_id, "assistant", self.welcome_message(), "text", {"first_run": True}))
        return history

    def welcome_message(self) -> str:
        capabilities = self.config["ui"].get("capabilities", [])[:3]
        capability_lines = "\n".join(f"• {capability}" for capability in capabilities) if capabilities else "• Handle day-to-day work"
        return (
            f"Hi, I'm {self.config['employee_name']}.\n\n"
            f"Role: {self.config['role_title']}.\n"
            f"Workflow: {self.config['workflow'].replace('_', ' ')}.\n\n"
            f"Core capabilities:\n{capability_lines}\n\n"
            "Send me work in natural language and I'll process it end-to-end."
        )

    async def submit_task(self, request: TaskRequest) -> dict[str, Any]:
        if self.engine is None:
            raise RuntimeError("Employee runtime service is not initialized.")

        conv_id = await self.ensure_conversation(request.conversation_id)
        await self.add_message(conv_id, "user", request.input, "text", dict(request.context))
        result = await self.engine.process_task(
            request.input,
            input_type=str(request.context.get("input_type", "chat")),
            metadata=request.context,
            conversation_id=conv_id,
        )
        task_id = result["task_id"]
        self.tasks[task_id] = result

        summary = self._result_summary(result)
        await self.add_message(conv_id, "assistant", summary, "status_update", {"task_id": task_id})
        approval_message = await self.add_message(
            conv_id,
            "assistant",
            summary,
            "approval_request",
            {
                "task_id": task_id,
                "status": "pending",
                "brief": self._result_card(result),
                "decision": "",
            },
        )
        self.approvals[approval_message["id"]] = approval_message
        return result

    def _result_summary(self, result: dict[str, Any]) -> str:
        return (
            str(result.get("response_summary"))
            or str(result.get("brief", {}).get("executive_summary", ""))
            or str(result.get("result_card", {}).get("executive_summary", "Task completed."))
        )

    def _result_card(self, result: dict[str, Any]) -> dict[str, Any]:
        if isinstance(result.get("result_card"), dict) and result["result_card"]:
            return result["result_card"]
        return result.get("brief", {})

    async def task_status(self, task_id: str) -> dict[str, Any]:
        if task_id not in self.tasks:
            raise KeyError(task_id)
        return self.tasks[task_id]

    async def task_brief(self, task_id: str) -> dict[str, Any]:
        task = await self.task_status(task_id)
        return self._result_card(task)

    async def list_approvals(self) -> list[dict[str, Any]]:
        return [approval for approval in self.approvals.values() if approval["metadata"].get("status") == "pending"]

    async def decide_approval(self, message_id: str, decision: str, note: str) -> dict[str, Any]:
        if message_id not in self.approvals:
            raise KeyError(message_id)
        approval = self.approvals[message_id]
        approval["metadata"]["status"] = decision
        approval["metadata"]["decision"] = decision
        approval["metadata"]["note"] = note
        if "audit_system" in self.components:
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
        if "audit_system" not in self.components:
            return []
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

    async def meta(self) -> dict[str, Any]:
        return {
            "employee_name": self.config["employee_name"],
            "role_title": self.config["role_title"],
            "workflow": self.config["workflow"],
            "badge": self.config["ui"].get("app_badge", ""),
            "capabilities": self.config["ui"].get("capabilities", []),
            "deployment_format": self.config["deployment_format"],
        }

    async def send_morning_briefing(self, conversation_id: str = "") -> dict[str, Any]:
        conv_id = await self.ensure_conversation(conversation_id)
        metrics = await self.metrics()
        content = (
            f"Morning briefing: {metrics['tasks_total']} tasks completed so far. "
            f"Average confidence {metrics['avg_confidence']}."
        )
        message = await self.add_message(conv_id, "system", content, "status_update", {"briefing": True})
        if self.tool_broker is not None and "email_tool" in self.config["tool_permissions"]:
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
    service = EmployeeRuntimeService(employee_id, config or {})

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

    @app.get("/api/v1/meta")
    async def meta() -> dict[str, Any]:
        await ensure_ready()
        return await service.meta()

    @app.post("/api/v1/chat")
    async def chat(request: TaskRequest) -> dict[str, Any]:
        await ensure_ready()
        result = await service.submit_task(request)
        return {"task_id": result["task_id"], "message_type": "brief_card", "data": service._result_card(result)}

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
            output=service._result_summary(result),
            brief=service._result_card(result),
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
                assert service.engine is not None
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
                        card = service._result_card(state)
                        summary = service._result_summary(state)
                        approval_message = await service.add_message(
                            conversation_id,
                            "assistant",
                            summary,
                            "approval_request",
                            {"task_id": task_id, "status": "pending", "brief": card},
                        )
                        service.approvals[approval_message["id"]] = approval_message
                        for token in summary.split():
                            await websocket.send_json({"type": "token", "content": f"{token} "})
                        await websocket.send_json({"type": "complete", "message_type": "brief_card", "data": card})
        except WebSocketDisconnect:
            return

    return app


def _normalize_runtime_config(employee_id: str, config: dict[str, Any]) -> dict[str, Any]:
    raw_manifest = config.get("manifest", config)
    workflow = str(raw_manifest.get("workflow", config.get("workflow", "legal_intake")))
    role_title = str(raw_manifest.get("role_title", config.get("employee_name", "Forge Employee")))
    employee_name = str(raw_manifest.get("employee_name", config.get("employee_name", employee_id)))

    components = raw_manifest.get("components") or [
        {"id": "text_processor", "category": "work", "config": {}},
        {"id": "document_analyzer", "category": "work", "config": {}},
        {"id": "draft_generator", "category": "work", "config": {}},
        {"id": "email_tool", "category": "tools", "config": {}},
        {"id": "operational_memory", "category": "data", "config": {}},
        {"id": "working_memory", "category": "data", "config": {}},
        {"id": "context_assembler", "category": "data", "config": {}},
        {"id": "org_context", "category": "data", "config": {}},
        {"id": "confidence_scorer", "category": "quality", "config": {}},
        {"id": "audit_system", "category": "quality", "config": {}},
        {"id": "input_protection", "category": "quality", "config": {}},
        {"id": "verification_layer", "category": "quality", "config": {}},
    ]
    tool_permissions = list(raw_manifest.get("tool_permissions") or [component["id"] for component in components if str(component["id"]).endswith("_tool")])
    capabilities = list(raw_manifest.get("ui", {}).get("capabilities") or config.get("primary_responsibilities", []))
    identity_layers = raw_manifest.get("identity_layers") or {
        "layer_1_core_identity": "You are a Forge AI Employee.",
        "layer_2_role_definition": config.get("system_identity", f"You are {employee_name}."),
        "layer_3_organizational_map": "Work with your supervisor and colleagues.",
        "layer_4_behavioral_rules": "Follow direct commands, then portal rules, then adaptive learning.",
        "layer_5_retrieved_context": "",
        "layer_6_self_awareness": f"Workflow {workflow}; tools {', '.join(tool_permissions)}.",
    }

    org_map = raw_manifest.get("org_map") or config.get("people", [])
    return {
        "employee_id": str(raw_manifest.get("employee_id", employee_id)),
        "org_id": str(raw_manifest.get("org_id", config.get("org_id", "demo-org"))),
        "employee_name": employee_name,
        "role_title": role_title,
        "workflow": workflow,
        "components": components,
        "tool_permissions": tool_permissions,
        "identity_layers": identity_layers,
        "ui": raw_manifest.get("ui", {"app_badge": "Hosted web", "capabilities": capabilities}),
        "org_map": org_map,
        "escalation_chain": config.get("escalation_chain", [contact.get("name", "") for contact in org_map[:1]]),
        "firm_info": config.get("firm_info", {}),
        "practice_areas": config.get("practice_areas", []),
        "default_attorney": config.get("default_attorney", "Forge Review"),
        "supervisor_email": config.get("supervisor_email", "supervisor@example.com"),
        "deployment_format": config.get("deployment_format", raw_manifest.get("deployment", {}).get("format", "web")),
        "redis_url": config.get("redis_url", ""),
        "email_fixtures": config.get("email_fixtures", []),
        "calendar_fixtures": config.get("calendar_fixtures", []),
        "message_fixtures": config.get("message_fixtures", []),
        "crm_fixtures": config.get("crm_fixtures", {}),
        "timezone": config.get("timezone", "America/New_York"),
    }
