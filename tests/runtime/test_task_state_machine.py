"""Unit tests for TaskStateMachine."""

from __future__ import annotations

import pytest

from employee_runtime.core.task_state_machine import InvalidTaskTransition, TaskStateMachine

machine = TaskStateMachine()


def test_legal_transitions() -> None:
    machine.validate("queued", "running")
    machine.validate("running", "completed")
    machine.validate("running", "failed")
    machine.validate("running", "awaiting_approval")
    machine.validate("running", "interrupted")
    machine.validate("awaiting_approval", "running")
    machine.validate("awaiting_approval", "failed")
    machine.validate("interrupted", "queued")
    machine.validate("failed", "queued")


def test_illegal_transitions_raise() -> None:
    with pytest.raises(InvalidTaskTransition):
        machine.validate("completed", "running")
    with pytest.raises(InvalidTaskTransition):
        machine.validate("completed", "failed")
    with pytest.raises(InvalidTaskTransition):
        machine.validate("failed", "running")
    with pytest.raises(InvalidTaskTransition):
        machine.validate("queued", "completed")


def test_terminal_statuses() -> None:
    assert machine.is_terminal("completed")
    assert machine.is_terminal("failed")
    assert not machine.is_terminal("running")
    assert not machine.is_terminal("queued")


def test_inflight_statuses() -> None:
    assert machine.is_inflight("queued")
    assert machine.is_inflight("running")
    assert machine.is_inflight("awaiting_approval")
    assert not machine.is_inflight("completed")
    assert not machine.is_inflight("interrupted")


def test_unknown_status_raises() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        machine.validate("not_a_real_status", "running")
