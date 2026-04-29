"""Load repo-backed structured commissioning fixtures."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from factory.models.requirements import EmployeeRequirements

FIXTURE_DIR = Path(__file__).resolve().parent / "fixture_data"
DEFAULT_FIXTURE_ORG_ID = UUID("00000000-0000-0000-0000-000000000001")


def load_requirements_fixture(
    name: str,
    *,
    org_id: UUID | str | None = None,
) -> EmployeeRequirements:
    """Load a structured EmployeeRequirements fixture by name."""
    fixture_path = FIXTURE_DIR / f"{name}_requirements.json"
    if not fixture_path.exists():
        available = ", ".join(sorted(path.stem.removesuffix("_requirements") for path in FIXTURE_DIR.glob("*_requirements.json")))
        raise ValueError(f"Unknown requirements fixture '{name}'. Available fixtures: {available}")

    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    payload["org_id"] = str(org_id or DEFAULT_FIXTURE_ORG_ID)
    return EmployeeRequirements.model_validate(payload)
