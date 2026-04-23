"""Task state machine for employee task lifecycle transitions."""

from __future__ import annotations


class InvalidTaskTransition(ValueError):
    """Raised when a requested status transition is not permitted."""


_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running"}),
    "running": frozenset({"completed", "failed", "awaiting_approval", "interrupted"}),
    "awaiting_approval": frozenset({"running", "failed"}),
    "interrupted": frozenset({"queued"}),
    "completed": frozenset(),
    "failed": frozenset({"queued"}),
}

ALL_STATUSES: frozenset[str] = frozenset(_TRANSITIONS.keys())
INFLIGHT_STATUSES: frozenset[str] = frozenset({"queued", "running", "awaiting_approval"})
TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "failed"})


class TaskStateMachine:
    """Validates legal task status transitions."""

    def validate(self, current_status: str, new_status: str) -> None:
        """Assert that a task may transition from current_status to new_status."""
        if current_status not in _TRANSITIONS:
            raise ValueError(
                f"Unknown current status '{current_status}'. Valid: {sorted(ALL_STATUSES)}"
            )
        if new_status not in _TRANSITIONS:
            raise ValueError(
                f"Unknown target status '{new_status}'. Valid: {sorted(ALL_STATUSES)}"
            )
        allowed = _TRANSITIONS[current_status]
        if new_status not in allowed:
            raise InvalidTaskTransition(
                f"Cannot transition task from '{current_status}' to '{new_status}'. "
                f"Allowed from '{current_status}': {sorted(allowed) or '(terminal)'}"
            )

    def is_terminal(self, status: str) -> bool:
        return status in TERMINAL_STATUSES

    def is_inflight(self, status: str) -> bool:
        return status in INFLIGHT_STATUSES
