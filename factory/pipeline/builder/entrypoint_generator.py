"""Generate the packaged employee entrypoint."""

from __future__ import annotations

from pathlib import Path

ENTRYPOINT_TEMPLATE = '''"""Forge Employee — auto-generated entry point."""
from __future__ import annotations

import json
from pathlib import Path

import uvicorn

from employee_runtime.core.api import create_employee_app


CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
CONFIG = json.loads(CONFIG_PATH.read_text())
CONFIG["static_dir"] = str(Path(__file__).resolve().parent / "static")
app = create_employee_app(CONFIG["employee_id"], CONFIG)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
'''


async def generate_entrypoint(build_dir: Path) -> None:
    """Create run.py in the build directory."""
    (build_dir / "run.py").write_text(ENTRYPOINT_TEMPLATE)
