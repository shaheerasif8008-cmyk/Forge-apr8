from __future__ import annotations

from pathlib import Path

from employee_runtime.modules.deliberation.schemas import Argument, Proposal

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "challenger.md"


class ChallengerRole:
    def __init__(self, model_client) -> None:
        self._model_client = model_client

    async def argue(self, proposal: Proposal, model: str) -> Argument:
        if self._model_client is None:
            return Argument(role="challenger", model=model, reasoning=f"Challenge proposal: {proposal.content}", key_points=["default concern"])
        return await self._model_client.structure(
            Argument,
            {
                "stance": "against",
                "proposal": proposal.model_dump(mode="json"),
                "model": model,
            },
            system_prompt=PROMPT_PATH.read_text(),
        )
