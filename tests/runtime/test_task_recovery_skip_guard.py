from __future__ import annotations

import importlib


def test_docker_availability_returns_false_when_binary_missing(monkeypatch) -> None:
    task_recovery = importlib.import_module("tests.runtime.test_task_recovery")

    def fake_run(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(task_recovery.subprocess, "run", fake_run)

    assert task_recovery._docker_available() is False
