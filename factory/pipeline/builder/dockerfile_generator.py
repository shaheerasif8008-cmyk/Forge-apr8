"""Generate the employee Dockerfile."""

from __future__ import annotations

from pathlib import Path


DOCKERFILE_TEMPLATE = """FROM python:3.12-slim

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

EXPOSE 8001
CMD ["python", "run.py"]
"""


async def generate_dockerfile(build_dir: Path) -> None:
    """Write the Dockerfile into the build directory."""
    (build_dir / "Dockerfile").write_text(DOCKERFILE_TEMPLATE)
