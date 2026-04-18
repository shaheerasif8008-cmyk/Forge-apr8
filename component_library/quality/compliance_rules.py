"""compliance_rules quality and governance component."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import httpx

from component_library.interfaces import ComponentHealth, QualityModule
from component_library.quality.schemas import PolicyDecision
from component_library.registry import register

POLICY_DIR = Path(__file__).resolve().parent / "policies"


@register("compliance_rules")
class ComplianceRules(QualityModule):
    component_id = "compliance_rules"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._opa_url = str(config.get("opa_url", "http://opa:8181")).rstrip("/")
        self._policy_name = str(config.get("policy_name", "legal"))
        self._conflicts = list(config.get("conflicts", []))
        self._use_opa_server = bool(config.get("use_opa_server", False))
        self._policy_dir = Path(str(config.get("policy_dir", POLICY_DIR)))
        if not self._policy_dir.is_absolute():
            self._policy_dir = POLICY_DIR.parent / self._policy_dir

    async def health_check(self) -> ComponentHealth:
        return ComponentHealth(healthy=True, detail=self._policy_name)

    def get_test_suite(self) -> list[str]:
        return ["tests/components/quality/test_compliance_rules.py"]

    async def evaluate(self, input_data: Any) -> PolicyDecision:
        payload = input_data if isinstance(input_data, dict) else {"content": str(input_data)}
        if self._use_opa_server:
            try:
                return await self._evaluate_with_opa_server(payload)
            except Exception:
                pass
        try:
            return await self._evaluate_with_cli_or_fallback(payload)
        except Exception:
            return self._evaluate_fallback(payload)

    async def _evaluate_with_opa_server(self, payload: dict[str, Any]) -> PolicyDecision:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.put(
                f"{self._opa_url}/v1/data/conflicts",
                json={"input": {"known": self._conflicts}},
            )
            violations_response = await client.post(
                f"{self._opa_url}/v1/data/forge/{self._policy_name}/violations",
                json={"input": payload},
            )
            allow_response = await client.post(
                f"{self._opa_url}/v1/data/forge/{self._policy_name}/allow",
                json={"input": payload},
            )
            violations_response.raise_for_status()
            allow_response.raise_for_status()
            violations = self._coerce_result_list(violations_response.json())
            allowed = bool(self._coerce_result_scalar(allow_response.json()))
            return PolicyDecision(
                allowed=allowed,
                violations=violations,
                required_remediation=self._remediation_for(violations),
            )

    async def _evaluate_with_cli_or_fallback(self, payload: dict[str, Any]) -> PolicyDecision:
        opa_path = shutil.which("opa")
        if opa_path is None:
            return self._evaluate_fallback(payload)

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "input.json"
            data_path = Path(temp_dir) / "data.json"
            input_path.write_text(json.dumps(payload))
            data_path.write_text(json.dumps({"conflicts": {"known": self._conflicts}}))
            violations_cmd = [
                opa_path,
                "eval",
                "--format",
                "json",
                "--data",
                str(self._policy_dir),
                "--data",
                str(data_path),
                "--input",
                str(input_path),
                f"data.forge.{self._policy_name}.violations",
            ]
            allow_cmd = [
                opa_path,
                "eval",
                "--format",
                "json",
                "--data",
                str(self._policy_dir),
                "--data",
                str(data_path),
                "--input",
                str(input_path),
                f"data.forge.{self._policy_name}.allow",
            ]
            violations_output = subprocess.run(violations_cmd, capture_output=True, text=True, check=True)
            allow_output = subprocess.run(allow_cmd, capture_output=True, text=True, check=True)
            violations = self._coerce_result_list(json.loads(violations_output.stdout))
            allowed = bool(self._coerce_result_scalar(json.loads(allow_output.stdout)))
            return PolicyDecision(
                allowed=allowed,
                violations=violations,
                required_remediation=self._remediation_for(violations),
            )

    def _evaluate_fallback(self, payload: dict[str, Any]) -> PolicyDecision:
        content = str(payload.get("content", ""))
        violations: list[str] = []
        entities = [str(entity) for entity in payload.get("entities", []) if entity]

        if self._policy_name == "legal":
            if str(payload.get("action_type", "")) == "email_send" and re.search(
                r"(?i)you should (sue|file)|i recommend (filing|suing)",
                content,
            ):
                violations.append("Contains direct legal advice - licensed attorney required")
            for entity in entities:
                if any(entity.lower() == conflict.lower() for conflict in self._conflicts):
                    violations.append(f"Conflict of interest detected: {entity}")
        elif self._policy_name == "healthcare":
            if re.search(r"(?i)patient|diagnosis|dob|ssn|medical record", content) and not bool(payload.get("scrubbed")):
                violations.append("Potential PHI detected - scrub or redact before delivery")

        return PolicyDecision(
            allowed=not violations,
            violations=violations,
            required_remediation=self._remediation_for(violations),
        )

    def _coerce_result_list(self, payload: dict[str, Any]) -> list[str]:
        result = self._coerce_result_scalar(payload)
        if isinstance(result, list):
            return [str(item) for item in result]
        return []

    def _coerce_result_scalar(self, payload: dict[str, Any]) -> Any:
        items = payload.get("result", [])
        if not items:
            return None
        expressions = items[0].get("expressions", [])
        if not expressions:
            return None
        return expressions[0].get("value")

    def _remediation_for(self, violations: list[str]) -> list[str]:
        remediation: list[str] = []
        for violation in violations:
            lowered = violation.lower()
            if "legal advice" in lowered:
                remediation.append("Route to a licensed attorney for review.")
            elif "conflict" in lowered:
                remediation.append("Pause delivery and run a formal conflict check.")
            elif "phi" in lowered:
                remediation.append("Scrub PHI before sharing the output.")
        return remediation
