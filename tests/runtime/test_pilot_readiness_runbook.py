from __future__ import annotations

from pathlib import Path


def test_pilot_readiness_runbook_covers_required_operator_proofs() -> None:
    runbook = Path("docs/PILOT_READINESS_RUNBOOK.md")

    assert runbook.exists()
    text = runbook.read_text(encoding="utf-8")

    required_markers = {
        "python3 scripts/pilot_readiness_smoke.py --pretty",
        "python3 scripts/prove_server_export.py --mode preflight",
        "python3 scripts/prove_server_export.py --mode full",
        "EMPLOYEE_API_KEY",
        "FORGE_STRICT_PROVIDERS",
        "pending_client_action",
        "degraded integrations",
    }

    missing = {marker for marker in required_markers if marker not in text}
    assert not missing
