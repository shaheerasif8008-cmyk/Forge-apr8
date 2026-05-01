from __future__ import annotations

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import prove_server_export as proof  # noqa: E402


def test_assign_available_host_port_rewrites_compose_when_default_port_is_busy(tmp_path: Path) -> None:
    bundle_dir = tmp_path / "bundle"
    bundle_dir.mkdir()
    compose_path = bundle_dir / "docker-compose.yml"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        busy_port = int(sock.getsockname()[1])
        compose_path.write_text(
            "services:\n"
            "  employee:\n"
            "    ports:\n"
            f"      - \"{busy_port}:8001\"\n"
        )
        port = proof._assign_available_host_port(bundle_dir)

    assert port != busy_port
    assert f'"{port}:8001"' in compose_path.read_text()


def test_supported_archetype_payloads_are_server_exports_without_federated_learning() -> None:
    assert set(proof.SUPPORTED_ARCHETYPES) == {"legal_intake", "executive_assistant", "accountant"}

    for archetype in proof.SUPPORTED_ARCHETYPES:
        payload = proof._commission_payload_for_archetype(archetype)

        assert payload["org_id"] == proof.DEFAULT_ORG_ID
        assert payload["deployment_format"] == "server"
        assert payload["deployment_target"] == "client_server"
        assert payload["employee_type"] in {"legal_intake_associate", "executive_assistant", "accountant"}
        assert payload["name"]
        assert payload["role_title"]
        assert payload["primary_responsibilities"]
        assert payload["required_tools"]
        assert payload["org_context"]["people"]
        assert "federated" not in str(payload).lower()


def test_default_commission_uses_selected_archetype(monkeypatch) -> None:
    ctx = proof.ProofContext(api_base="http://forge.test/api/v1", factory_env={}, employee_env={}, auth_token="token")
    ctx.archetype = "executive_assistant"
    calls = []

    def fake_request_json(method, url, *, payload=None, headers=None, timeout=30):
        calls.append({"method": method, "url": url, "payload": payload, "headers": headers})
        return 202, {"build_id": "build-123"}

    monkeypatch.setattr(proof, "_request_json", fake_request_json)

    proof._commission_build(ctx)

    assert ctx.build_id == "build-123"
    assert calls[0]["payload"]["employee_type"] == "executive_assistant"
    assert calls[0]["payload"]["name"] == "Morgan Executive Assistant"
