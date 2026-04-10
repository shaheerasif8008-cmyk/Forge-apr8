"""Standard employee API — every deployed employee exposes this FastAPI interface."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel


class TaskRequest(BaseModel):
    input: str
    context: dict[str, object] = {}


class TaskResponse(BaseModel):
    task_id: str
    status: str
    output: str = ""


def create_employee_app(employee_id: str) -> FastAPI:
    """Create the standard FastAPI app for a deployed employee."""
    app = FastAPI(title=f"Employee API — {employee_id}", version="1.0.0")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "employee_id": employee_id}

    @app.post("/tasks", response_model=TaskResponse)
    async def submit_task(request: TaskRequest) -> TaskResponse:
        """Submit a task to the employee for execution."""
        # TODO: route through EmployeeEngine
        return TaskResponse(task_id="stub", status="queued")

    return app
