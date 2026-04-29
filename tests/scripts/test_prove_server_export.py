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
