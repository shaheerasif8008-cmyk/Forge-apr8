"""Smoke tests for ORM model definitions (no live DB required)."""

from __future__ import annotations

from factory.models.orm import (
    AuditEventRow,
    Base,
    BlueprintRow,
    BuildRow,
    ClientOrgRow,
    ClientRow,
    DeploymentRow,
    EmployeeRequirementsRow,
)


def test_all_tables_registered_in_metadata() -> None:
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "client_orgs",
        "clients",
        "employee_requirements",
        "blueprints",
        "builds",
        "deployments",
        "audit_events",
    }
    assert expected == table_names


def test_client_org_columns() -> None:
    cols = {c.name for c in ClientOrgRow.__table__.columns}
    assert {"id", "name", "slug", "industry", "tier", "contact_email", "created_at"} <= cols


def test_employee_requirements_jsonb_columns() -> None:
    cols = {c.name: c for c in EmployeeRequirementsRow.__table__.columns}
    jsonb_cols = {
        "primary_responsibilities", "kpis", "required_tools",
        "required_data_sources", "communication_channels",
        "compliance_frameworks", "org_context",
    }
    for col_name in jsonb_cols:
        assert col_name in cols, f"Missing JSONB column: {col_name}"
        # SQLAlchemy type name for JSONB contains "JSON"
        assert "JSON" in type(cols[col_name].type).__name__.upper(), (
            f"Column {col_name} should be JSONB"
        )


def test_blueprint_jsonb_columns() -> None:
    cols = {c.name: c for c in BlueprintRow.__table__.columns}
    for col_name in ("components", "custom_code_specs", "autonomy_profile"):
        assert col_name in cols
        assert "JSON" in type(cols[col_name].type).__name__.upper()


def test_build_jsonb_columns() -> None:
    cols = {c.name: c for c in BuildRow.__table__.columns}
    for col_name in ("logs", "artifacts", "test_report"):
        assert col_name in cols


def test_deployment_has_unique_build_id() -> None:
    table = DeploymentRow.__table__
    unique_constraints = {
        frozenset(c.name for c in uc.columns)
        for uc in table.constraints
        if hasattr(uc, "columns") and uc.__class__.__name__ == "UniqueConstraint"
    }
    assert frozenset({"build_id"}) in unique_constraints


def test_audit_event_has_hash_chain_column() -> None:
    cols = {c.name for c in AuditEventRow.__table__.columns}
    assert "hash_chain" in cols
    assert "occurred_at" in cols


def test_audit_event_compute_hash_deterministic() -> None:
    payload = {"action": "build.started", "build_id": "abc-123"}
    h1 = AuditEventRow.compute_hash("", payload)
    h2 = AuditEventRow.compute_hash("", payload)
    assert h1 == h2
    assert len(h1) == 64  # SHA-256 hex


def test_audit_event_hash_chain_changes_with_prev() -> None:
    payload = {"action": "build.started"}
    h_first = AuditEventRow.compute_hash("", payload)
    h_second = AuditEventRow.compute_hash(h_first, payload)
    assert h_first != h_second
