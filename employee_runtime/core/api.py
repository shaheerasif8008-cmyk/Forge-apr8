"""Standard employee API — every deployed employee exposes this FastAPI interface."""

from __future__ import annotations

import asyncio
import importlib
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text

from component_library.component_factory import create_components
from employee_runtime.core.auth import (
    authorize_request,
    authorize_websocket,
    runtime_auth_config_from_dict,
)
from employee_runtime.core.conversation_repository import (
    ConversationRepository,
    InMemoryConversationRepository,
    SqlAlchemyConversationRepository,
)
from employee_runtime.core.engine import EmployeeEngine
from employee_runtime.core.kernel import classify_task, create_task_plan, estimate_roi, task_plan_to_context
from employee_runtime.core.runtime_db import initialize_runtime_database, normalize_org_uuid
from employee_runtime.core.task_repository import (
    InMemoryTaskRepository,
    SqlAlchemyTaskRepository,
    TaskRepository,
)
from employee_runtime.core.tool_broker import ToolBroker
from employee_runtime.modules.behavior_manager import BehaviorManager
from employee_runtime.modules.pulse_engine import DailyLoopRequest, PulseEngine
from employee_runtime.shared.orm import KnowledgeChunkRow
from employee_runtime.workflow_packs import get_workflow_pack


OPTIONAL_COMPONENT_MODULES = (
    "component_library.data.context_assembler",
    "component_library.data.knowledge_base",
    "component_library.data.operational_memory",
    "component_library.data.org_context",
    "component_library.data.working_memory",
    "component_library.models.anthropic_provider",
    "component_library.models.litellm_router",
    "component_library.quality.audit_system",
    "component_library.quality.autonomy_manager",
    "component_library.quality.approval_manager",
    "component_library.quality.adversarial_review",
    "component_library.quality.compliance_rules",
    "component_library.quality.confidence_scorer",
    "component_library.quality.explainability",
    "component_library.quality.input_protection",
    "component_library.quality.verification_layer",
    "component_library.tools.calendar_tool",
    "component_library.tools.crm_tool",
    "component_library.tools.email_tool",
    "component_library.tools.file_storage_tool",
    "component_library.tools.messaging_tool",
    "component_library.work.communication_manager",
    "component_library.work.document_analyzer",
    "component_library.work.draft_generator",
    "component_library.work.scheduler_manager",
    "component_library.work.text_processor",
    "component_library.work.workflow_executor",
)


def _import_packaged_component_modules() -> None:
    for module_name in OPTIONAL_COMPONENT_MODULES:
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            raise


_import_packaged_component_modules()


class NoStoreStaticFiles(StaticFiles):
    """Serve generated employee apps without reusing stale localhost assets."""

    async def get_response(self, path: str, scope: dict[str, Any]) -> Response:
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response


class TaskRequest(BaseModel):
    task_id: str = ""
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


class DirectCommandPayload(BaseModel):
    command: str


class PortalQuietHoursPayload(BaseModel):
    description: str = "No non-urgent messages after quiet hours."
    after_hour: int = 17
    suppress_non_urgent: bool = True
    channels: list[str] = Field(default_factory=lambda: ["email", "messaging"])


class AdaptivePatternPayload(BaseModel):
    description: str
    after_hour: int = 17
    suppress_non_urgent: bool = True
    channels: list[str] = Field(default_factory=lambda: ["email", "messaging"])
    observed_for: str = ""


class CorrectionPayload(BaseModel):
    message: str
    corrected_output: str = ""


class MemoryEntryPayload(BaseModel):
    value: dict[str, Any] = Field(default_factory=dict)
    category: str = ""


class KnowledgeDocumentPayload(BaseModel):
    document_id: str
    document: str
    title: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    replace_existing: bool = False


class EmployeeRuntimeService:
    def __init__(self, employee_id: str, config: dict[str, Any]) -> None:
        self.employee_id = employee_id
        self.config = _normalize_runtime_config(employee_id, config)
        self.components: dict[str, Any] = {}
        self.engine: EmployeeEngine | None = None
        self.tool_broker: ToolBroker | None = None
        self.pulse_engine: PulseEngine | None = None
        self.behavior_manager: BehaviorManager | None = None
        self.conversation_repository: ConversationRepository | None = None
        self.task_repository: TaskRepository | None = None
        self._runtime_db_handle: Any | None = None
        self._session_factory: Any | None = None
        self._initialization_error = ""
        self._startup_recovery_summary: dict[str, Any] = {
            "recovered_at": "",
            "interrupted_task_ids": [],
        }

    async def initialize(self) -> None:
        if self.engine is not None or self._initialization_error:
            return
        try:
            await self._initialize_persistence()
            await self._reconcile_inflight_tasks()
        except Exception as exc:
            self._initialization_error = f"runtime_persistence_unavailable: {exc}"
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
            autonomy_manager=self.components.get("autonomy_manager"),
            risk_tier=str(self.config.get("risk_tier", "MEDIUM")),
            tenant_policy=self.config.get("tenant_policy", {}),
            required_approver=str(self.config.get("supervisor_email", "supervisor")),
        )
        if "autonomy_manager" in self.components and self.components.get("audit_system"):
            if hasattr(self.components["autonomy_manager"], "set_audit_logger"):
                self.components["autonomy_manager"].set_audit_logger(self.components["audit_system"].log_event)
        if "adversarial_review" in self.components:
            model_client = self.components.get("litellm_router") or self.components.get("anthropic_provider")
            if hasattr(self.components["adversarial_review"], "set_model_client"):
                self.components["adversarial_review"].set_model_client(model_client)
            if hasattr(self.components["adversarial_review"], "set_audit_logger") and self.components.get("audit_system"):
                self.components["adversarial_review"].set_audit_logger(self.components["audit_system"].log_event)
        if "explainability" in self.components and self.components.get("audit_system"):
            if hasattr(self.components["explainability"], "set_audit_logger"):
                self.components["explainability"].set_audit_logger(self.components["audit_system"].log_event)
        self.engine = EmployeeEngine(
            self.config["workflow"],
            self.components,
            {
                "employee_id": self.employee_id,
                "org_id": self.config["org_id"],
                "workflow_graph": self.config.get("workflow_graph", {}),
            },
        )
        self.behavior_manager = BehaviorManager(
            operational_memory=self.components["operational_memory"],
            audit_logger=self.components.get("audit_system", None).log_event if self.components.get("audit_system") else None,
            employee_id=self.employee_id,
            org_id=str(self.config["org_id"]),
            timezone=str(self.config.get("timezone", "America/New_York")),
        )
        self.pulse_engine = PulseEngine(
            employee_id=self.employee_id,
            workflow=self.config["workflow"],
            engine=self.engine,
            tool_broker=self.tool_broker,
            components=self.components,
            config=self.config,
            add_message=self.add_message,
            metrics_provider=self.metrics,
            behavior_manager=self.behavior_manager,
        )

    async def _initialize_persistence(self) -> None:
        if self.conversation_repository is not None:
            return

        provided_repository = self.config.get("conversation_repository")
        provided_task_repository = self.config.get("task_repository")
        if provided_repository is not None:
            self.conversation_repository = provided_repository
            self.task_repository = provided_task_repository or InMemoryTaskRepository()
            return

        session_factory = self.config.get("session_factory")
        if session_factory is not None:
            self.config["org_id"] = normalize_org_uuid(self.config["org_id"])
            self._session_factory = session_factory
            self.conversation_repository = SqlAlchemyConversationRepository(session_factory)
            self.task_repository = provided_task_repository or SqlAlchemyTaskRepository(
                session_factory,
                org_id=str(self.config["org_id"]),
            )
            return

        database_url = str(self.config.get("employee_database_url", "")).strip()
        if database_url:
            handle = await initialize_runtime_database(
                database_url=database_url,
                raw_org_id=str(self.config["org_id"]),
                employee_id=self.employee_id,
                auto_init=bool(self.config.get("employee_db_auto_init", True)),
            )
            self._runtime_db_handle = handle
            self._session_factory = handle.session_factory
            self.config["org_id"] = handle.org_uuid
            self.conversation_repository = SqlAlchemyConversationRepository(handle.session_factory)
            self.task_repository = SqlAlchemyTaskRepository(
                handle.session_factory,
                org_id=str(handle.org_uuid),
            )
            return

        self.conversation_repository = InMemoryConversationRepository()
        self.task_repository = provided_task_repository or InMemoryTaskRepository()

    async def shutdown(self) -> None:
        if self._runtime_db_handle is not None:
            await self._runtime_db_handle.close()
            self._runtime_db_handle = None

    @property
    def initialization_error(self) -> str:
        return self._initialization_error

    def _component_config(self) -> dict[str, dict[str, Any]]:
        component_config = {component["id"]: dict(component.get("config", {})) for component in self.config["components"]}
        component_config.setdefault("operational_memory", {}).update(
            {
                "org_id": self.config["org_id"],
                "employee_id": self.employee_id,
                "session_factory": self._session_factory,
            }
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
                "session_factory": self._session_factory,
                "operational_memory": None,
                "conversation_repository": self.conversation_repository,
                "employee_id": self.employee_id,
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
        component_config.setdefault("audit_system", {}).update({"session_factory": self._session_factory})
        component_config.setdefault("adversarial_review", {}).update(
            {"deliberation_council": self.config.get("deliberation_council", {})}
        )
        component_config.setdefault("autonomy_manager", {}).update(
            {
                "required_approver": self.config.get("supervisor_email", "supervisor"),
                "tenant_overrides": self.config.get("tenant_policy", {}),
            }
        )
        component_config.setdefault("explainability", {}).update(
            {
                "session_factory": self._session_factory,
                "employee_id": self.employee_id,
                "org_id": self.config["org_id"],
            }
        )
        component_config.setdefault("compliance_rules", {}).update(
            {
                "policy_name": self.config.get("policy_name", "legal"),
                "conflicts": self.config.get("conflicts", []),
            }
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

    def _workflow_packs(self) -> list[Any]:
        pack_ids = self.config.get("workflow_packs", ["executive_assistant_pack"])
        packs = []
        for pack_id in pack_ids:
            packs.append(get_workflow_pack(str(pack_id)))
        return packs

    async def ensure_conversation(self, conversation_id: str = "") -> str:
        conv_id = conversation_id or self._default_conversation_id()
        if self.conversation_repository is None:
            raise RuntimeError("Conversation repository is not initialized.")
        await self.conversation_repository.ensure_conversation(
            conv_id,
            self.employee_id,
            str(self.config["org_id"]),
        )
        return conv_id

    async def _reconcile_inflight_tasks(self) -> None:
        if self.task_repository is None:
            return
        interrupted = await self.task_repository.mark_inflight_tasks_interrupted(
            self.employee_id,
            reason="runtime_restarted_before_task_completion",
        )
        self._startup_recovery_summary = {
            "recovered_at": datetime.now(UTC).isoformat(),
            "interrupted_task_ids": [task["task_id"] for task in interrupted],
        }
        for task in interrupted:
            conversation_id = str(task.get("conversation_id", ""))
            if not conversation_id or self.conversation_repository is None:
                continue
            await self.add_message(
                conversation_id,
                "system",
                "A running task was interrupted by a runtime restart and marked interrupted.",
                "status_update",
                {"task_id": task["task_id"], "status": "interrupted", "recovery": True},
            )

    def _recovery_policy(self) -> dict[str, Any]:
        return {
            "task_state_source": "employee_tasks",
            "approval_state_source": "conversation_messages",
            "history_state_source": "conversation_messages",
            "persistent_memory_sources": ["operational_memory", "knowledge_base"],
            "ephemeral_memory_sources": ["working_memory"],
            "inflight_restart_behavior": "mark_interrupted_and_notify",
            "restart_requires_healthcheck": True,
            "health_endpoint": "/api/v1/health",
            "recovery_endpoint": "/api/v1/runtime/recovery",
        }

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self.conversation_repository is None:
            raise RuntimeError("Conversation repository is not initialized.")
        return await self.conversation_repository.add_message(
            conversation_id,
            self.employee_id,
            str(self.config["org_id"]),
            role,
            content,
            message_type,
            metadata or {},
        )

    async def history(self, conversation_id: str) -> list[dict[str, Any]]:
        conv_id = await self.ensure_conversation(conversation_id)
        assert self.conversation_repository is not None
        history = await self.conversation_repository.history(conv_id, self.employee_id)
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
        if self.task_repository is None:
            raise RuntimeError("Task repository is not initialized.")

        conv_id = await self.ensure_conversation(request.conversation_id)
        task_id = request.task_id or str(uuid4())
        input_type = str(request.context.get("input_type", "chat"))
        await self.task_repository.create_task(
            task_id=task_id,
            employee_id=self.employee_id,
            org_id=str(self.config["org_id"]),
            conversation_id=conv_id,
            input_text=request.input,
            input_type=input_type,
            input_metadata=dict(request.context),
        )
        await self.add_message(conv_id, "user", request.input, "text", dict(request.context))
        await self.task_repository.update_task(
            task_id,
            self.employee_id,
            {
                "status": "running",
                "started_at": datetime.now(UTC),
            },
        )
        await self.add_message(
            conv_id,
            "system",
            "Task received and running.",
            "status_update",
            {"task_id": task_id, "status": "running"},
        )
        delay_seconds = float(request.context.get("_test_runtime_delay_seconds", 0) or 0)
        if delay_seconds > 0:
            await asyncio.sleep(min(delay_seconds, 30.0))
        packs = self._workflow_packs()
        classification = classify_task(request.input, packs)
        plan = create_task_plan(task_input=request.input, classification=classification, packs=packs)
        kernel_context = task_plan_to_context(plan)
        enriched_context = {**dict(request.context), **kernel_context}
        try:
            result = await self.engine.process_task(
                request.input,
                input_type=input_type,
                metadata=enriched_context,
                conversation_id=conv_id,
                task_id=task_id,
            )
        except Exception as exc:
            await self.task_repository.update_task(
                task_id,
                self.employee_id,
                {
                    "status": "failed",
                    "error": str(exc),
                    "completed_at": datetime.now(UTC),
                },
            )
            await self.add_message(
                conv_id,
                "system",
                f"Task failed: {exc}",
                "status_update",
                {"task_id": task_id, "status": "failed"},
            )
            raise

        final_status = "awaiting_approval" if result.get("requires_human_approval") else "completed"
        summary = self._result_summary(result)
        card = self._result_card(result)
        workflow_output = dict(result.get("workflow_output", {}))
        workflow_output["kernel"] = {
            **kernel_context["kernel"],
            "classification": classification.model_dump(mode="json"),
        }
        persisted = await self.task_repository.update_task(
            task_id,
            self.employee_id,
            {
                "status": final_status,
                "response_summary": summary,
                "result_card": card,
                "workflow_output": workflow_output,
                "state": dict(result),
                "requires_human_approval": bool(result.get("requires_human_approval", False)),
                "completed_at": datetime.now(UTC) if final_status == "completed" else None,
                "error": "",
                "interruption_reason": "",
            },
        )

        await self.add_message(conv_id, "assistant", summary, "status_update", {"task_id": task_id, "status": final_status})
        if final_status == "awaiting_approval":
            await self.add_message(
                conv_id,
                "assistant",
                summary,
                "approval_request",
                {
                    "task_id": task_id,
                    "status": "pending",
                    "brief": card,
                    "decision": "",
                },
            )
        return persisted

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
        if self.task_repository is None:
            raise RuntimeError("Task repository is not initialized.")
        task = await self.task_repository.get_task(task_id, self.employee_id)
        if task is None:
            raise KeyError(task_id)
        return task

    async def task_brief(self, task_id: str) -> dict[str, Any]:
        task = await self.task_status(task_id)
        return self._result_card(task)

    async def record_correction(self, task_id: str, payload: CorrectionPayload) -> dict[str, Any]:
        task = await self.task_status(task_id)
        correction_key = _normalize_correction_key(payload.message)
        prior = await self.components["operational_memory"].list_by_category("mistake_correction")
        repeat_count = 1 + sum(
            1
            for record in prior
            if isinstance(record.get("value"), dict) and record["value"].get("correction_key") == correction_key
        )
        escalated_to_forge = repeat_count >= 2
        acknowledgement = "You're right. I misread that. Correcting now."
        if payload.corrected_output:
            acknowledgement = f"{acknowledgement} Updated direction: {payload.corrected_output}"

        correction = {
            "task_id": task_id,
            "correction_key": correction_key,
            "message": payload.message,
            "corrected_output": payload.corrected_output,
            "acknowledgement": acknowledgement,
            "repeat_count": repeat_count,
            "escalated_to_forge": escalated_to_forge,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        await self.components["operational_memory"].store(
            f"correction:{task_id}:{repeat_count}",
            correction,
            "mistake_correction",
        )
        await self.components["operational_memory"].store(
            f"learning:{correction_key}",
            {
                "source": "local_correction",
                "last_feedback": payload.message,
                "corrected_output": payload.corrected_output,
                "repeat_count": repeat_count,
            },
            "local_learning",
        )
        if escalated_to_forge:
            await self.components["operational_memory"].store(
                f"forge_escalation:{correction_key}",
                {
                    "task_id": task_id,
                    "reason": "repeated_correction_pattern",
                    "repeat_count": repeat_count,
                    "latest_feedback": payload.message,
                },
                "forge_escalation",
            )

        task["correction_record"] = correction
        if payload.corrected_output:
            task["response_summary"] = payload.corrected_output
            if isinstance(task.get("result_card"), dict):
                task["result_card"]["executive_summary"] = payload.corrected_output
        if self.task_repository is not None:
            await self.task_repository.update_task(
                task_id,
                self.employee_id,
                {
                    "response_summary": task.get("response_summary", ""),
                    "result_card": dict(task.get("result_card", {})),
                    "state": dict(task),
                },
            )
        conversation_id = str(task.get("conversation_id", ""))
        if conversation_id:
            await self.add_message(
                conversation_id,
                "assistant",
                acknowledgement,
                "status_update",
                {"task_id": task_id, "correction": True, "escalated_to_forge": escalated_to_forge},
            )
        if "audit_system" in self.components:
            await self.components["audit_system"].log_event(
                employee_id=self.employee_id,
                org_id=str(self.config["org_id"]),
                event_type="mistake_corrected",
                details=correction,
            )
        return correction

    async def list_corrections(self) -> list[dict[str, Any]]:
        records = await self.components["operational_memory"].list_by_category("mistake_correction")
        return [
            record["value"]
            for record in records
            if isinstance(record.get("value"), dict)
        ]

    async def memory_snapshot(self) -> dict[str, Any]:
        categories = (
            "general",
            "daily_loop",
            "behavior_rule",
            "local_learning",
            "mistake_correction",
            "forge_escalation",
            "preference",
        )
        snapshot: dict[str, list[dict[str, Any]]] = {}
        for category in categories:
            items = await self.components["operational_memory"].list_by_category(category)
            snapshot[category] = [
                {
                    "key": item.get("key", ""),
                    "value": item.get("value", {}),
                }
                for item in items[:10]
            ]
        return snapshot

    async def list_operational_memory(
        self,
        *,
        query: str = "",
        category: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        operational_memory = self.components.get("operational_memory")
        if operational_memory is None:
            return []
        records = await operational_memory.search(query, category=category or None, limit=limit)
        return [
            {
                "key": str(record.get("key", "")),
                "value": record.get("value", {}),
                "category": str(record.get("category", "general")),
            }
            for record in records
        ]

    async def update_operational_memory(
        self,
        key: str,
        value: dict[str, Any],
        *,
        category: str = "",
    ) -> dict[str, Any]:
        operational_memory = self.components.get("operational_memory")
        if operational_memory is None:
            raise RuntimeError("operational_memory_unavailable")
        existing = await operational_memory.retrieve(key)
        resolved_category = (
            category
            or (str(existing.get("category", "")) if isinstance(existing, dict) else "")
            or "general"
        )
        record = await operational_memory.store(key, value, resolved_category)
        return {
            "key": str(record.get("key", key)),
            "value": record.get("value", value),
            "category": str(record.get("category", resolved_category)),
        }

    async def delete_operational_memory(self, key: str) -> dict[str, Any]:
        operational_memory = self.components.get("operational_memory")
        if operational_memory is None:
            raise RuntimeError("operational_memory_unavailable")
        await operational_memory.delete(key)
        return {"deleted": True, "key": key}

    async def working_memory_snapshot(self) -> list[dict[str, Any]]:
        working_memory = self.components.get("working_memory")
        if working_memory is None or not hasattr(working_memory, "get_all"):
            return []
        task_ids: list[str] = []
        if self.task_repository is not None:
            recent_tasks = await self.task_repository.list_recent_tasks(self.employee_id, limit=20)
            task_ids = [str(task["task_id"]) for task in recent_tasks]
        snapshots: list[dict[str, Any]] = []
        for task_id in reversed(task_ids[-20:]):
            values = await working_memory.get_all(task_id)
            if not values:
                continue
            snapshots.append({"task_id": task_id, "values": values})
        return snapshots

    async def list_knowledge_documents(self) -> list[dict[str, Any]]:
        knowledge_base = self.components.get("knowledge_base")
        if knowledge_base is None:
            return []

        chunks: list[dict[str, Any]] = []
        session_factory = getattr(knowledge_base, "_session_factory", None)
        tenant_id = str(getattr(knowledge_base, "_tenant_id", ""))
        if session_factory is None:
            memory_chunks = getattr(knowledge_base, "_memory_chunks", [])
            chunks = [
                {
                    "document_id": str(chunk.get("document_id", "")),
                    "chunk_index": int(chunk.get("chunk_index", 0)),
                    "content": str(chunk.get("content", "")),
                    "metadata": chunk.get("metadata", {}),
                }
                for chunk in memory_chunks
                if str(chunk.get("tenant_id", "")) == tenant_id
            ]
        else:
            async with session_factory() as session:
                result = await session.execute(
                    select(KnowledgeChunkRow)
                    .where(KnowledgeChunkRow.tenant_id == getattr(knowledge_base, "_tenant_id"))
                    .order_by(KnowledgeChunkRow.document_id, KnowledgeChunkRow.chunk_index)
                )
                rows = result.scalars().all()
            chunks = [
                {
                    "document_id": str(row.document_id),
                    "chunk_index": row.chunk_index,
                    "content": row.content,
                    "metadata": row.chunk_metadata,
                    "created_at": row.created_at.isoformat(),
                }
                for row in rows
            ]

        grouped: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            document_id = str(chunk.get("document_id", ""))
            metadata = chunk.get("metadata", {})
            document = grouped.setdefault(
                document_id,
                {
                    "document_id": document_id,
                    "title": str(metadata.get("title") or document_id),
                    "metadata": metadata,
                    "chunk_count": 0,
                    "chunks": [],
                    "created_at": str(chunk.get("created_at", "")),
                },
            )
            document["chunk_count"] += 1
            document["chunks"].append(
                {
                    "chunk_index": int(chunk.get("chunk_index", 0)),
                    "content": str(chunk.get("content", "")),
                }
            )
            if not document["created_at"] and chunk.get("created_at"):
                document["created_at"] = str(chunk["created_at"])

        documents = list(grouped.values())
        documents.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return documents

    async def _clear_knowledge_document(self, document_id: str) -> None:
        knowledge_base = self.components.get("knowledge_base")
        if knowledge_base is None:
            return
        normalized_id = knowledge_base._coerce_uuid(document_id)  # noqa: SLF001
        session_factory = getattr(knowledge_base, "_session_factory", None)
        if session_factory is None:
            memory_chunks = getattr(knowledge_base, "_memory_chunks", [])
            knowledge_base._memory_chunks = [  # noqa: SLF001
                chunk
                for chunk in memory_chunks
                if not (
                    str(chunk.get("tenant_id", "")) == str(getattr(knowledge_base, "_tenant_id", ""))
                    and str(chunk.get("document_id", "")) == str(normalized_id)
                )
            ]
            return

        async with session_factory() as session:
            await session.execute(
                delete(KnowledgeChunkRow).where(
                    KnowledgeChunkRow.tenant_id == getattr(knowledge_base, "_tenant_id"),
                    KnowledgeChunkRow.document_id == normalized_id,
                )
            )
            await session.commit()

    async def upsert_knowledge_document(
        self,
        *,
        document_id: str,
        document: str,
        title: str = "",
        metadata: dict[str, Any] | None = None,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        knowledge_base = self.components.get("knowledge_base")
        if knowledge_base is None:
            raise RuntimeError("knowledge_base_unavailable")

        payload_metadata = dict(metadata or {})
        if title:
            payload_metadata.setdefault("title", title)
        if replace_existing:
            await self._clear_knowledge_document(document_id)

        await knowledge_base.ingest(
            document_id=document_id,
            document=document,
            metadata=payload_metadata,
        )
        normalized_id = str(knowledge_base._coerce_uuid(document_id))  # noqa: SLF001
        documents = await self.list_knowledge_documents()
        return next(
            (item for item in documents if item["document_id"] == normalized_id),
            {
                "document_id": normalized_id,
                "title": title or normalized_id,
                "metadata": payload_metadata,
                "chunk_count": 0,
                "chunks": [],
                "created_at": "",
            },
        )

    async def upload_document(
        self,
        *,
        filename: str,
        content: bytes | None = None,
        file_path: str = "",
        metadata: dict[str, Any] | None = None,
        replace_existing: bool = False,
    ) -> dict[str, Any]:
        if content is None:
            if not file_path:
                raise RuntimeError("document_content_missing")
            content = Path(file_path).read_bytes()

        stored_metadata = dict(metadata or {})
        stored_metadata.setdefault("title", filename)
        if file_path:
            stored_metadata.setdefault("source_path", file_path)

        file_storage = self.components.get("file_storage_tool")
        storage_result: dict[str, Any] = {}
        if file_storage is not None:
            storage_result = await file_storage.invoke(
                "upload",
                {
                    "key": f"documents/{filename}",
                    "content_bytes": content,
                },
            )
            stored_metadata.setdefault("storage_key", storage_result.get("key", ""))

        document_ingestion = self.components.get("document_ingestion")
        if document_ingestion is not None:
            extract_payload: dict[str, Any] = {"content": content}
            if file_path:
                extract_payload["file_path"] = file_path
            extracted = await document_ingestion.invoke("extract_text", extract_payload)
            document_text = str(extracted.get("text", ""))
        else:
            document_text = content.decode("utf-8", errors="replace")

        knowledge_base = self.components.get("knowledge_base")
        if knowledge_base is None:
            return {
                "document_id": filename,
                "title": filename,
                "metadata": stored_metadata,
                "chunk_count": 0,
                "chunks": [],
            }

        document_id = str(stored_metadata.get("document_id") or filename)
        return await self.upsert_knowledge_document(
            document_id=document_id,
            document=document_text,
            title=filename,
            metadata=stored_metadata,
            replace_existing=replace_existing,
        )

    async def updates_status(self) -> dict[str, Any]:
        learning_enabled = True
        settings = await self.get_settings()
        if isinstance(settings.get("advanced"), dict) and "learning_enabled" in settings["advanced"]:
            learning_enabled = bool(settings["advanced"]["learning_enabled"])
        behavior_rules = await self.list_behavior_rules()
        corrections = await self.list_corrections()
        return {
            "security": {"status": "supported", "mode": "factory-managed"},
            "learning": {
                "enabled": learning_enabled,
                "local_corrections": len(corrections),
            },
            "modules": {
                "installed_components": [component["id"] for component in self.config["components"]],
            },
            "policies": {
                "active_behavior_rules": len(behavior_rules),
            },
        }

    async def list_approvals(self) -> list[dict[str, Any]]:
        if self.conversation_repository is None:
            return []
        return await self.conversation_repository.list_pending_approvals(self.employee_id)

    async def decide_approval(self, message_id: str, decision: str, note: str) -> dict[str, Any]:
        approvals = await self.list_approvals()
        approval = next((item for item in approvals if item["id"] == message_id), None)
        if approval is None or self.conversation_repository is None:
            raise KeyError(message_id)
        metadata = dict(approval.get("metadata", {}))
        metadata["status"] = decision
        metadata["decision"] = decision
        metadata["note"] = note
        approval = await self.conversation_repository.update_message_metadata(
            message_id,
            self.employee_id,
            metadata,
        )
        task_id = str(metadata.get("task_id", ""))
        if task_id and self.task_repository is not None:
            next_status = "completed" if decision in {"approve", "modify"} else "interrupted"
            await self.task_repository.update_task(
                task_id,
                self.employee_id,
                {
                    "status": next_status,
                    "completed_at": datetime.now(UTC),
                    "interruption_reason": "" if next_status == "completed" else f"approval_{decision}",
                },
            )
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
        profile = self._default_settings_profile()
        stored_profile: dict[str, Any] = next(
            (
                pref["value"]
                for pref in prefs
                if pref.get("key") == "pref:settings_profile" and isinstance(pref.get("value"), dict)
            ),
            {},
        )
        if isinstance(stored_profile, dict):
            profile = _merge_nested_dicts(profile, stored_profile)
        for pref in prefs:
            key = str(pref.get("key", "")).removeprefix("pref:")
            value = pref.get("value", {}).get("value", pref.get("value"))
            if key == "quiet_hours":
                profile["communication_preferences"]["quiet_hours"] = value
        return profile

    async def put_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        current = await self.get_settings()
        next_settings = _merge_nested_dicts(current, values)
        await self.components["operational_memory"].store(
            "pref:settings_profile",
            next_settings,
            "preference",
        )
        quiet_hours = next_settings["communication_preferences"]["quiet_hours"]
        await self.components["operational_memory"].store(
            "pref:quiet_hours",
            {"value": quiet_hours},
            "preference",
        )
        if self.behavior_manager is not None:
            quiet_hour = _parse_quiet_hours(quiet_hours)
            if quiet_hour is not None:
                await self.behavior_manager.set_portal_quiet_hours(
                    rule_id="portal-quiet-hours",
                    description=f"Portal quiet-hours preference from settings: {quiet_hours}",
                    after_hour=quiet_hour,
                    suppress_non_urgent=True,
                    channels=["email", "messaging"],
                    metadata={"source": "settings", "value": quiet_hours},
                )
        return await self.get_settings()

    def _default_settings_profile(self) -> dict[str, Any]:
        return {
            "communication_preferences": {
                "preferred_channels": ["email", "messaging"],
                "briefing_frequency": "daily",
                "tone": "balanced",
                "quiet_hours": "after_5pm",
            },
            "approval_rules": {
                "required_actions": ["external_send", "contract_approval"],
                "dollar_threshold": 1000,
                "recipient_threshold": 5,
            },
            "authority_limits": {
                "max_autonomous_action_value": 1000,
                "max_recipients": 5,
            },
            "organizational_map": {
                "people": list(self.config.get("org_map", [])),
            },
            "integrations": {
                "connected_tools": list(self.config.get("tool_permissions", [])),
            },
            "advanced": {
                "confidence_threshold": 0.72,
                "council_enabled": "adversarial_review" in self.components,
                "learning_enabled": True,
            },
        }

    async def list_behavior_rules(self) -> list[dict[str, Any]]:
        if self.behavior_manager is None:
            return []
        rules = await self.behavior_manager.list_rules()
        return [rule.model_dump(mode="json") for rule in rules]

    async def add_direct_command(self, command: str) -> dict[str, Any]:
        if self.behavior_manager is None:
            raise RuntimeError("Behavior manager is not initialized.")
        rule = await self.behavior_manager.add_direct_command(command)
        return rule.model_dump(mode="json")

    async def add_portal_rule(self, payload: PortalQuietHoursPayload) -> dict[str, Any]:
        if self.behavior_manager is None:
            raise RuntimeError("Behavior manager is not initialized.")
        rule = await self.behavior_manager.set_portal_quiet_hours(
            rule_id="portal-quiet-hours",
            description=payload.description,
            after_hour=payload.after_hour,
            suppress_non_urgent=payload.suppress_non_urgent,
            channels=payload.channels,
        )
        return rule.model_dump(mode="json")

    async def add_adaptive_pattern(self, payload: AdaptivePatternPayload) -> dict[str, Any]:
        if self.behavior_manager is None:
            raise RuntimeError("Behavior manager is not initialized.")
        rule = await self.behavior_manager.add_adaptive_pattern(
            description=payload.description,
            after_hour=payload.after_hour,
            suppress_non_urgent=payload.suppress_non_urgent,
            channels=payload.channels,
            metadata={"observed_for": payload.observed_for},
        )
        return rule.model_dump(mode="json")

    async def resolve_behavior(
        self,
        *,
        urgency: str = "normal",
        channel: str = "email",
        current_time: str = "",
    ) -> dict[str, Any]:
        if self.behavior_manager is None:
            raise RuntimeError("Behavior manager is not initialized.")
        resolved_time = datetime.fromisoformat(current_time) if current_time else None
        resolution = await self.behavior_manager.resolve_quiet_hours(
            urgency=urgency,
            channel=channel,
            current_time=resolved_time,
        )
        return resolution.model_dump(mode="json")

    async def activity(self, limit: int = 50) -> list[dict[str, Any]]:
        activity: list[dict[str, Any]] = []
        if "audit_system" in self.components:
            activity.extend(await self.components["audit_system"].get_trail(self.employee_id))
        if "explainability" in self.components:
            records = await self.components["explainability"].get_records_for_employee()
            activity.extend(
                {
                    "event_type": "reasoning_captured",
                    "record_id": str(record.record_id),
                    "task_id": str(record.task_id),
                    "node_id": record.node_id,
                    "decision": record.decision,
                    "confidence": record.confidence,
                    "occurred_at": record.created_at.isoformat(),
                }
                for record in records
            )
        return sorted(
            activity,
            key=lambda item: str(item.get("occurred_at", "")),
        )[-limit:]

    async def metrics(self) -> dict[str, Any]:
        activity = await self.activity()
        completed = [
            event
            for event in activity
            if event["event_type"] == "task_completed"
            and isinstance(event.get("details"), dict)
            and event["details"].get("node") == "log_completion"
        ]
        outputs = [event for event in activity if event["event_type"] == "output_produced"]
        approvals = [event for event in activity if event["event_type"] == "approval_decided"]
        corrections = await self.list_corrections()
        packs = self._workflow_packs()
        roi = estimate_roi(
            packs,
            completed_tasks=len(completed),
            escalations=len([event for event in activity if event["event_type"] == "approval_requested"]),
            rework_events=len(corrections),
        )
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
            "roi": roi,
        }

    async def metrics_dashboard(self) -> dict[str, Any]:
        base_metrics = await self.metrics()
        activity = await self.activity(limit=250)
        approvals = await self.list_approvals()
        pending_approvals = len(
            [item for item in approvals if isinstance(item.get("metadata"), dict) and item["metadata"].get("status") == "pending"]
        )

        days: list[str] = []
        task_counts: dict[str, int] = {}
        confidence_points: list[dict[str, Any]] = []
        now = datetime.now(UTC)
        for offset in range(6, -1, -1):
            day = (now.date()).fromordinal(now.date().toordinal() - offset)
            label = day.isoformat()
            days.append(label)
            task_counts[label] = 0

        category_counts = {"decision": 0, "communication": 0, "error": 0, "system": 0}
        for event in activity:
            event_type = str(event.get("event_type", ""))
            details = event.get("details", {}) if isinstance(event.get("details"), dict) else {}
            occurred_at = str(event.get("occurred_at", ""))
            date_label = occurred_at[:10]
            if event_type == "task_completed" and date_label in task_counts:
                task_counts[date_label] += 1
            if event_type == "approval_decided":
                category_counts["decision"] += 1
            elif "message" in event_type or "briefing" in event_type or "communication" in event_type:
                category_counts["communication"] += 1
            elif "error" in event_type or "failed" in event_type:
                category_counts["error"] += 1
            else:
                category_counts["system"] += 1
            if event_type == "output_produced" and "confidence" in details:
                confidence_points.append(
                    {
                        "label": occurred_at or f"output-{len(confidence_points) + 1}",
                        "confidence": float(details.get("confidence", 0.0)),
                    }
                )

        return {
            "kpis": {
                "tasks_total": base_metrics["tasks_total"],
                "avg_confidence": base_metrics["avg_confidence"],
                "pending_approvals": pending_approvals,
                "avg_duration_seconds": base_metrics["avg_duration_seconds"],
                "estimated_minutes_saved": dict(base_metrics.get("roi", {})).get("estimated_minutes_saved", 0.0),
            },
            "tasks_by_day": [{"date": label, "tasks": task_counts[label]} for label in days],
            "approval_mix": [
                {"name": decision, "value": int(count)}
                for decision, count in dict(base_metrics.get("approval_mix", {})).items()
            ],
            "activity_mix": [{"name": name, "value": value} for name, value in category_counts.items()],
            "confidence_trend": confidence_points[-12:],
        }

    async def recovery_status(self) -> dict[str, Any]:
        task_counts = await self.task_repository.task_counts(self.employee_id) if self.task_repository is not None else {}
        return {
            "policy": self._recovery_policy(),
            "startup_summary": dict(self._startup_recovery_summary),
            "task_counts": task_counts,
        }

    async def meta(self) -> dict[str, Any]:
        return {
            "employee_name": self.config["employee_name"],
            "role_title": self.config["role_title"],
            "workflow": self.config["workflow"],
            "badge": self.config["ui"].get("app_badge", ""),
            "capabilities": self.config["ui"].get("capabilities", []),
            "deployment_format": self.config["deployment_format"],
            "enabled_sidebar_panels": self.config.get("enabled_sidebar_panels", []),
            "workflow_packs": self.config.get("workflow_packs", []),
            "kernel_baseline": self.config.get("kernel_baseline", {}),
        }

    async def get_reasoning_records(self, task_id: str) -> list[dict[str, Any]]:
        explainability = self.components.get("explainability")
        if explainability is None:
            return []
        records = await explainability.get_records(task_id)
        return [record.model_dump(mode="json") for record in records]

    async def get_reasoning_record(self, record_id: str) -> dict[str, Any] | None:
        explainability = self.components.get("explainability")
        if explainability is None:
            return None
        record = await explainability.get_record(record_id)
        return None if record is None else record.model_dump(mode="json")

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

    async def run_daily_loop(self, request: DailyLoopRequest) -> dict[str, Any]:
        if self.pulse_engine is None:
            raise RuntimeError("Pulse engine is not initialized.")
        conv_id = await self.ensure_conversation(request.conversation_id)
        report = await self.pulse_engine.run_daily_loop(
            DailyLoopRequest(
                conversation_id=conv_id,
                max_items=request.max_items,
                current_time=request.current_time,
            )
        )
        return report.model_dump(mode="json")

    async def latest_daily_loop_report(self) -> dict[str, Any] | None:
        operational_memory = self.components.get("operational_memory")
        if operational_memory is None:
            return None
        record = await operational_memory.retrieve("daily_loop:latest")
        if record is None:
            return None
        value = record.get("value", {})
        if not isinstance(value, dict):
            return None
        return value


def create_employee_app(employee_id: str, config: dict[str, Any] | None = None) -> FastAPI:
    service = EmployeeRuntimeService(employee_id, config or {})
    auth_config = runtime_auth_config_from_dict(service.config)

    async def ensure_ready() -> None:
        await service.initialize()
        if service.initialization_error:
            raise HTTPException(status_code=503, detail=service.initialization_error)
        await service.ensure_conversation()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if (
            os.environ.get("ENVIRONMENT", "development") == "production"
            and not os.environ.get("EMPLOYEE_API_KEY", "").strip()
        ):
            raise RuntimeError(
                "EMPLOYEE_API_KEY must be set in production. "
                'Generate one: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        await service.initialize()
        try:
            yield
        finally:
            await service.shutdown()

    app = FastAPI(title=f"Employee API — {employee_id}", version="1.0.0", lifespan=lifespan)
    app.state.runtime_service = service

    @app.middleware("http")
    async def authenticate_api_requests(request: Request, call_next):
        if request.url.path in {"/health", "/api/v1/health", "/api/v1/ready", "/api/v1/recovery"}:
            return await call_next(request)
        if not request.url.path.startswith("/api/v1"):
            return await call_next(request)
        try:
            authorize_request(request, auth_config)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        return await call_next(request)

    async def _health(response: Response) -> dict[str, str]:
        _ = response
        return {"status": "ok", "employee_id": employee_id}

    @app.get("/health")
    async def health_legacy(response: Response) -> dict[str, str]:
        return await _health(response)

    @app.get("/api/v1/health")
    async def health(response: Response) -> dict[str, str]:
        return await _health(response)

    @app.get("/api/v1/ready")
    async def employee_readiness(response: Response) -> dict[str, object]:
        deps: list[dict[str, object]] = []
        await service.initialize()

        if service.initialization_error:
            deps.append(
                {
                    "name": "runtime",
                    "healthy": False,
                    "detail": service.initialization_error,
                }
            )
        else:
            deps.append({"name": "runtime", "healthy": True})

        if service._session_factory is None:
            deps.append({"name": "postgres", "healthy": False, "detail": "session_factory not initialised"})
        else:
            try:
                async with service._session_factory() as session:
                    await session.execute(text("SELECT 1"))
                deps.append({"name": "postgres", "healthy": True})
            except Exception as exc:  # noqa: BLE001
                deps.append({"name": "postgres", "healthy": False, "detail": str(exc)})

        ready = all(bool(dep.get("healthy")) for dep in deps)
        if not ready:
            response.status_code = 503
        return {"ready": ready, "dependencies": deps}

    @app.get("/api/v1/recovery")
    async def employee_recovery() -> dict[str, object]:
        await service.initialize()
        if service.task_repository is None:
            return {"interrupted_tasks": -1, "detail": "task_repository not initialised"}
        try:
            interrupted = await service.task_repository.get_interrupted_tasks(employee_id=service.employee_id)
            return {
                "interrupted_tasks": len(interrupted),
                "task_ids": [task.get("task_id") for task in interrupted],
            }
        except Exception as exc:  # noqa: BLE001
            return {"interrupted_tasks": -1, "detail": str(exc)}

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
            status=str(result.get("status", "completed")),
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

    @app.post("/api/v1/tasks/{task_id}/corrections")
    async def correct_task(task_id: str, payload: CorrectionPayload) -> dict[str, Any]:
        await ensure_ready()
        try:
            return await service.record_correction(task_id, payload)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="task_not_found") from exc

    @app.get("/api/v1/corrections")
    async def get_corrections() -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.list_corrections()

    @app.get("/api/v1/memory")
    async def get_memory() -> dict[str, Any]:
        await ensure_ready()
        return await service.memory_snapshot()

    @app.get("/api/v1/memory/ops")
    async def get_operational_memory(
        query: str = "",
        category: str = "",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.list_operational_memory(query=query, category=category, limit=limit)

    @app.patch("/api/v1/memory/ops/{key:path}")
    async def patch_operational_memory(key: str, payload: MemoryEntryPayload) -> dict[str, Any]:
        await ensure_ready()
        return await service.update_operational_memory(key, payload.value, category=payload.category)

    @app.delete("/api/v1/memory/ops/{key:path}")
    async def delete_operational_memory(key: str) -> dict[str, Any]:
        await ensure_ready()
        return await service.delete_operational_memory(key)

    @app.get("/api/v1/memory/working")
    async def get_working_memory() -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.working_memory_snapshot()

    @app.get("/api/v1/memory/kb/documents")
    async def get_knowledge_documents() -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.list_knowledge_documents()

    @app.post("/api/v1/memory/kb/documents")
    async def upsert_knowledge_document(payload: KnowledgeDocumentPayload) -> dict[str, Any]:
        await ensure_ready()
        return await service.upsert_knowledge_document(
            document_id=payload.document_id,
            document=payload.document,
            title=payload.title,
            metadata=payload.metadata,
            replace_existing=payload.replace_existing,
        )

    @app.get("/api/v1/updates")
    async def get_updates() -> dict[str, Any]:
        await ensure_ready()
        return await service.updates_status()

    @app.get("/api/v1/runtime/recovery")
    async def get_recovery_status() -> dict[str, Any]:
        await ensure_ready()
        return await service.recovery_status()

    @app.get("/api/v1/activity")
    async def get_activity(limit: int = 50) -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.activity(limit=limit)

    @app.get("/api/v1/reasoning/{task_id}")
    async def get_reasoning(task_id: str) -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.get_reasoning_records(task_id)

    @app.get("/api/v1/reasoning/record/{record_id}")
    async def get_reasoning_record(record_id: str) -> dict[str, Any]:
        await ensure_ready()
        record = await service.get_reasoning_record(record_id)
        if record is None:
            raise HTTPException(status_code=404, detail="reasoning_record_not_found")
        return record

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

    @app.post("/api/v1/approvals/{message_id}/resolve")
    async def resolve_approval(message_id: str, payload: ApprovalDecision) -> dict[str, Any]:
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

    @app.patch("/api/v1/settings")
    async def patch_settings(payload: SettingsPayload) -> dict[str, Any]:
        await ensure_ready()
        return await service.put_settings(payload.values)

    @app.get("/api/v1/behavior/rules")
    async def get_behavior_rules() -> list[dict[str, Any]]:
        await ensure_ready()
        return await service.list_behavior_rules()

    @app.post("/api/v1/behavior/direct-commands")
    async def add_direct_command(payload: DirectCommandPayload) -> dict[str, Any]:
        await ensure_ready()
        return await service.add_direct_command(payload.command)

    @app.post("/api/v1/behavior/portal-rules")
    async def add_portal_rule(payload: PortalQuietHoursPayload) -> dict[str, Any]:
        await ensure_ready()
        return await service.add_portal_rule(payload)

    @app.post("/api/v1/behavior/adaptive-patterns")
    async def add_adaptive_pattern(payload: AdaptivePatternPayload) -> dict[str, Any]:
        await ensure_ready()
        return await service.add_adaptive_pattern(payload)

    @app.get("/api/v1/behavior/resolution")
    async def get_behavior_resolution(
        urgency: str = "normal",
        channel: str = "email",
        current_time: str = "",
    ) -> dict[str, Any]:
        await ensure_ready()
        return await service.resolve_behavior(urgency=urgency, channel=channel, current_time=current_time)

    @app.get("/api/v1/metrics")
    async def get_metrics() -> dict[str, Any]:
        await ensure_ready()
        return await service.metrics()

    @app.get("/api/v1/metrics/dashboard")
    async def get_metrics_dashboard() -> dict[str, Any]:
        await ensure_ready()
        return await service.metrics_dashboard()

    @app.post("/api/v1/documents/upload")
    async def upload_document(
        file: UploadFile | None = File(default=None),
        file_path: str = Form(default=""),
        metadata: str = Form(default="{}"),
        replace_existing: bool = Form(default=False),
    ) -> dict[str, Any]:
        await ensure_ready()
        parsed_metadata = json.loads(metadata) if metadata else {}
        content = await file.read() if file is not None else None
        filename = file.filename if file is not None else Path(file_path).name
        if not filename:
            raise HTTPException(status_code=400, detail="document_missing")
        return await service.upload_document(
            filename=filename,
            content=content,
            file_path=file_path,
            metadata=parsed_metadata,
            replace_existing=replace_existing,
        )

    @app.post("/api/v1/autonomy/daily-loop")
    async def run_daily_loop(request: DailyLoopRequest) -> dict[str, Any]:
        await ensure_ready()
        return await service.run_daily_loop(request)

    @app.get("/api/v1/autonomy/daily-loop/latest")
    async def get_latest_daily_loop() -> dict[str, Any]:
        await ensure_ready()
        report = await service.latest_daily_loop_report()
        if report is None:
            raise HTTPException(status_code=404, detail="daily_loop_not_found")
        return report

    @app.websocket("/api/v1/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        if not await authorize_websocket(websocket, auth_config):
            return
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
                task_id = str(payload.get("task_id") or uuid4())
                if service.task_repository is None:
                    await websocket.send_json({"type": "error", "message": "task_repository_unavailable"})
                    continue
                await service.task_repository.create_task(
                    task_id=task_id,
                    employee_id=service.employee_id,
                    org_id=str(service.config["org_id"]),
                    conversation_id=conversation_id,
                    input_text=payload["content"],
                    input_type="chat",
                    input_metadata={},
                )
                await service.task_repository.update_task(
                    task_id,
                    service.employee_id,
                    {"status": "running", "started_at": datetime.now(UTC)},
                )
                assert service.engine is not None
                packs = service._workflow_packs()
                classification = classify_task(payload["content"], packs)
                plan = create_task_plan(task_input=payload["content"], classification=classification, packs=packs)
                kernel_context = task_plan_to_context(plan)
                async for event in service.engine.process_task_streaming(
                    payload["content"],
                    metadata=kernel_context,
                    conversation_id=conversation_id,
                    task_id=task_id,
                ):
                    if event["type"] == "status":
                        await websocket.send_json({"type": "status", "node": event["node"], "status": event["status"]})
                    elif event["type"] == "complete":
                        state = event["state"]
                        card = service._result_card(state)
                        summary = service._result_summary(state)
                        final_status = "awaiting_approval" if state.get("requires_human_approval") else "completed"
                        workflow_output = dict(state.get("workflow_output", {}))
                        workflow_output["kernel"] = {
                            **kernel_context["kernel"],
                            "classification": classification.model_dump(mode="json"),
                        }
                        await service.task_repository.update_task(
                            task_id,
                            service.employee_id,
                            {
                                "status": final_status,
                                "response_summary": summary,
                                "result_card": card,
                                "workflow_output": workflow_output,
                                "state": dict(state),
                                "requires_human_approval": bool(state.get("requires_human_approval", False)),
                                "completed_at": datetime.now(UTC) if final_status == "completed" else None,
                            },
                        )
                        message = await service.add_message(
                            conversation_id,
                            "assistant",
                            summary,
                            "approval_request" if final_status == "awaiting_approval" else "status_update",
                            {"task_id": task_id, "status": "pending" if final_status == "awaiting_approval" else final_status, "brief": card},
                        )
                        for token in summary.split():
                            await websocket.send_json({"type": "token", "content": f"{token} "})
                        await websocket.send_json(
                            {
                                "type": "complete",
                                "message_type": message.get("message_type", "brief_card"),
                                "message_id": message.get("id"),
                                "task_id": task_id,
                                "status": final_status,
                                "data": card,
                                "kernel": workflow_output["kernel"],
                            }
                        )
        except WebSocketDisconnect:
            return

    static_dir = str(service.config.get("static_dir", "")).strip()
    if static_dir:
        static_path = Path(static_dir)
        if not static_path.is_absolute():
            static_path = Path.cwd() / static_path
        if static_path.exists():
            app.mount("/", NoStoreStaticFiles(directory=static_path, html=True), name="employee-frontend")

    return app


def _normalize_runtime_config(employee_id: str, config: dict[str, Any]) -> dict[str, Any]:
    raw_manifest = config.get("manifest", config)
    workflow = str(raw_manifest.get("workflow", config.get("workflow", "legal_intake")))
    role_title = str(raw_manifest.get("role_title", config.get("employee_name", "Forge Employee")))
    employee_name = str(raw_manifest.get("employee_name", config.get("employee_name", employee_id)))

    raw_components = raw_manifest.get("components") or _default_components_for_workflow(workflow)
    components = [_normalize_component_descriptor(component) for component in raw_components]
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
    normalized_people: list[dict[str, str]] = []
    for person in org_map:
        if not isinstance(person, dict):
            continue
        normalized_people.append(
            {
                "name": str(person.get("name", "")),
                "role": str(person.get("role", "Colleague")),
                "email": str(
                    person.get("email")
                    or person.get("contact")
                    or person.get("value")
                    or config.get("supervisor_email", "supervisor@example.com")
                ),
                "communication_preference": str(
                    person.get("communication_preference")
                    or person.get("communication_channel")
                    or "email"
                ),
                "relationship": str(
                    person.get("relationship")
                    or person.get("relationship_type")
                    or "colleague"
                ),
            }
        )
    return {
        "employee_id": str(raw_manifest.get("employee_id", employee_id)),
        "org_id": str(raw_manifest.get("org_id", config.get("org_id", "demo-org"))),
        "employee_name": employee_name,
        "role_title": role_title,
        "workflow": workflow,
        "workflow_graph": raw_manifest.get("workflow_graph", config.get("workflow_graph", {})),
        "risk_tier": str(raw_manifest.get("risk_tier", config.get("risk_tier", "MEDIUM"))).upper(),
        "tenant_policy": dict(config.get("tenant_policy", raw_manifest.get("tenant_policy", {})) or {}),
        "policy_name": str(config.get("policy_name", raw_manifest.get("policy_name", "legal"))),
        "conflicts": list(config.get("conflicts", raw_manifest.get("conflicts", [])) or []),
        "components": components,
        "tool_permissions": tool_permissions,
        "identity_layers": identity_layers,
        "ui": raw_manifest.get("ui", {"app_badge": "Hosted web", "capabilities": capabilities}),
        "org_map": normalized_people,
        "escalation_chain": config.get("escalation_chain", [contact.get("name", "") for contact in normalized_people[:1]]),
        "firm_info": config.get("firm_info", {}),
        "practice_areas": config.get("practice_areas", []),
        "default_attorney": config.get("default_attorney", "Forge Review"),
        "supervisor_email": config.get("supervisor_email", "supervisor@example.com"),
        "deployment_format": config.get("deployment_format", raw_manifest.get("deployment", {}).get("format", "web")),
        "enabled_sidebar_panels": raw_manifest.get(
            "enabled_sidebar_panels",
            config.get("enabled_sidebar_panels", raw_manifest.get("ui", {}).get("enabled_sidebar_panels", [])),
        ),
        "workflow_packs": raw_manifest.get("workflow_packs", config.get("workflow_packs", ["executive_assistant_pack"])),
        "kernel_baseline": raw_manifest.get("kernel_baseline", config.get("kernel_baseline", {})),
        "redis_url": config.get("redis_url", ""),
        "email_fixtures": config.get("email_fixtures", []),
        "calendar_fixtures": config.get("calendar_fixtures", []),
        "message_fixtures": config.get("message_fixtures", []),
        "crm_fixtures": config.get("crm_fixtures", {}),
        "deliberation_council": config.get(
            "deliberation_council",
            raw_manifest.get("deliberation_council", {}),
        ),
        "timezone": config.get("timezone", "America/New_York"),
        "employee_database_url": config.get("employee_database_url", raw_manifest.get("employee_database_url", "")),
        "employee_db_auto_init": config.get("employee_db_auto_init", raw_manifest.get("employee_db_auto_init", True)),
        "static_dir": config.get("static_dir", raw_manifest.get("static_dir", "")),
        "auth_required": config.get("auth_required", raw_manifest.get("auth_required", False)),
        "api_auth_token": config.get("api_auth_token", raw_manifest.get("api_auth_token", "")),
        "session_factory": config.get("session_factory"),
        "conversation_repository": config.get("conversation_repository"),
        "task_repository": config.get("task_repository"),
    }


def _default_components_for_workflow(workflow: str) -> list[dict[str, Any]]:
    if workflow == "legal_intake":
        return [
            {
                "id": "litellm_router",
                "category": "models",
                "config": {
                    "primary_model": "openrouter/anthropic/claude-3.5-sonnet",
                    "fallback_model": "openrouter/anthropic/claude-3.5-haiku",
                },
            },
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
            {"id": "autonomy_manager", "category": "quality", "config": {}},
            {"id": "explainability", "category": "quality", "config": {}},
            {"id": "input_protection", "category": "quality", "config": {}},
            {"id": "verification_layer", "category": "quality", "config": {}},
        ]
    return [
        {"id": "workflow_executor", "category": "work", "config": {}},
        {"id": "communication_manager", "category": "work", "config": {}},
        {"id": "scheduler_manager", "category": "work", "config": {}},
        {"id": "email_tool", "category": "tools", "config": {}},
        {"id": "calendar_tool", "category": "tools", "config": {}},
        {"id": "messaging_tool", "category": "tools", "config": {}},
        {"id": "crm_tool", "category": "tools", "config": {}},
        {"id": "operational_memory", "category": "data", "config": {}},
        {"id": "working_memory", "category": "data", "config": {}},
        {"id": "context_assembler", "category": "data", "config": {}},
        {"id": "org_context", "category": "data", "config": {}},
        {"id": "audit_system", "category": "quality", "config": {}},
        {"id": "autonomy_manager", "category": "quality", "config": {}},
        {"id": "explainability", "category": "quality", "config": {}},
        {"id": "input_protection", "category": "quality", "config": {}},
    ]


def _normalize_component_descriptor(component: Any) -> dict[str, Any]:
    if not isinstance(component, dict):
        raise TypeError("Component descriptor must be a mapping.")
    return {
        "id": str(component.get("id", component.get("component_id", ""))),
        "category": str(component.get("category", "")),
        "config": dict(component.get("config", {})),
    }


def _parse_quiet_hours(value: Any) -> int | None:
    lowered = str(value).strip().lower()
    if not lowered:
        return None
    if lowered == "after_5pm":
        return 17
    if lowered == "after_6pm":
        return 18
    if lowered == "after_7pm":
        return 19
    return None


def _normalize_correction_key(value: str) -> str:
    return "-".join(str(value).strip().lower().split())[:120]


def _merge_nested_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_nested_dicts(merged[key], value)
        else:
            merged[key] = value
    return merged
