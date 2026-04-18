from __future__ import annotations

from pathlib import Path

from employee_runtime.modules.deliberation.schemas import Argument, SupervisorReport, Verdict

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "supervisor.md"


class ProcessSupervisor:
    def __init__(self, model_client) -> None:
        self._model_client = model_client

    async def supervise(
        self,
        advocates: list[Argument],
        challengers: list[Argument],
        verdict: Verdict,
    ) -> SupervisorReport:
        if self._model_client is not None:
            return await self._model_client.structure(
                SupervisorReport,
                {
                    "advocates": [argument.model_dump(mode="json") for argument in advocates],
                    "challengers": [argument.model_dump(mode="json") for argument in challengers],
                    "verdict": verdict.model_dump(mode="json"),
                },
                system_prompt=PROMPT_PATH.read_text(),
            )
        advocate_reasoning = [argument.reasoning.strip() for argument in advocates]
        challenger_reasoning = [argument.reasoning.strip() for argument in challengers]
        issues: list[str] = []
        if advocate_reasoning and len(set(advocate_reasoning)) == 1 and len(advocate_reasoning) > 1:
            issues.append("advocate_echo_chamber")
        if challenger_reasoning and len(set(challenger_reasoning)) == 1 and len(challenger_reasoning) > 1:
            issues.append("challenger_echo_chamber")
        if not any(
            any(point in challenge.key_points for point in advocate.key_points)
            for advocate in advocates
            for challenge in challengers
        ):
            issues.append("sides_argued_past_each_other")
        rerun_needed = bool(issues)
        return SupervisorReport(
            rerun_needed=rerun_needed,
            reason="; ".join(issues) if issues else "debate acceptable",
            issues=issues,
        )
