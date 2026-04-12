"""Generate environment-variable documentation for packaged employees."""

from __future__ import annotations

from pathlib import Path

ENV_EXAMPLE = """# Employee runtime environment
ENVIRONMENT=production
REDIS_URL=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
OPENROUTER_API_KEY=
"""


async def generate_env_example(build_dir: Path) -> None:
    """Write .env.example into the build directory."""
    (build_dir / ".env.example").write_text(ENV_EXAMPLE)
