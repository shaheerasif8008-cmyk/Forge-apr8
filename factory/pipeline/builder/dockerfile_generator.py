"""Generate the employee Dockerfile."""

from __future__ import annotations

from pathlib import Path

DOCKERFILE_TEMPLATE = """FROM node:20-alpine AS frontend

WORKDIR /app/portal/employee_app
COPY portal/employee_app/package*.json ./
RUN npm ci
COPY portal/employee_app ./
RUN npm run build

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \\
    build-essential curl libpq-dev \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /app/portal/employee_app/out ./static

EXPOSE 8001
CMD ["python", "run.py"]
"""


async def generate_dockerfile(build_dir: Path) -> None:
    """Write the Dockerfile into the build directory."""
    (build_dir / "Dockerfile").write_text(DOCKERFILE_TEMPLATE)
