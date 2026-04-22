from __future__ import annotations

import re
from pathlib import Path


IMPORT_PATTERN = re.compile(r"^\s*(from|import)\s+factory(?:\.|\b)", re.MULTILINE)


def test_shipped_runtime_and_component_code_do_not_import_factory_namespace() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    shipped_roots = [
        repo_root / "employee_runtime",
        repo_root / "component_library",
    ]
    violations: list[str] = []

    for root in shipped_roots:
        for path in root.rglob("*.py"):
            if "tests" in path.parts:
                continue
            if IMPORT_PATTERN.search(path.read_text()):
                violations.append(str(path.relative_to(repo_root)))

    assert violations == []
