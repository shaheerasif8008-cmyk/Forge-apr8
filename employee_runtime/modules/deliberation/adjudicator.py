from __future__ import annotations

from pathlib import Path

from employee_runtime.modules.deliberation.schemas import Argument, Proposal, Verdict

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "adjudicator.md"


class AdjudicatorRole:
    def __init__(self, model_client) -> None:
        self._model_client = model_client

    async def adjudicate(
        self,
        proposal: Proposal,
        advocates: list[Argument],
        challengers: list[Argument],
        model: str,
    ) -> Verdict:
        if self._model_client is None:
            concerns = [point for argument in challengers for point in argument.key_points]
            return Verdict(
                approved=not concerns,
                confidence=0.7 if not concerns else 0.45,
                majority_concerns=concerns,
                dissenting_views=[argument.reasoning for argument in advocates if concerns],
                reasoning="Default adjudication path.",
            )
        return await self._model_client.structure(
            Verdict,
            {
                "proposal": proposal.model_dump(mode="json"),
                "advocates": [argument.model_dump(mode="json") for argument in advocates],
                "challengers": [argument.model_dump(mode="json") for argument in challengers],
                "model": model,
            },
            system_prompt=PROMPT_PATH.read_text(),
        )
