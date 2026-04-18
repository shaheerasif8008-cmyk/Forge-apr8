from __future__ import annotations

import pytest

from component_library.work.data_analyzer import DataAnalyzer
from component_library.work.schemas import DataAnalysisRequest


class _MockCompleter:
    component_id = "custom-model"

    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, system_prompt: str, user_message: str) -> str:
        self.calls += 1
        return f"LLM summary: {user_message[:40]}"


@pytest.mark.anyio
async def test_data_analyzer_happy_path_with_rows() -> None:
    analyzer = DataAnalyzer()
    await analyzer.initialize({})
    report = await analyzer.execute(
        DataAnalysisRequest(
            rows=[
                {"team": "A", "revenue": 10, "cost": 6},
                {"team": "B", "revenue": 12, "cost": 5},
                {"team": "C", "revenue": 80, "cost": 7},
            ],
            question="Which row looks unusual?",
        )
    )
    assert report.key_metrics["row_count"] == 3
    assert report.schema[0].name in {"cost", "revenue", "team"}
    assert report.anomalies


@pytest.mark.anyio
async def test_data_analyzer_accepts_csv() -> None:
    analyzer = DataAnalyzer()
    await analyzer.initialize({})
    report = await analyzer.execute(
        DataAnalysisRequest(
            csv_data="team,revenue\nA,10\nB,15\n",
        )
    )
    assert report.key_metrics["row_count"] == 2
    assert any(column.name == "revenue" for column in report.schema)


@pytest.mark.anyio
async def test_data_analyzer_errors_without_query_runner() -> None:
    analyzer = DataAnalyzer()
    await analyzer.initialize({})
    with pytest.raises(ValueError, match="no query_runner"):
        await analyzer.execute(DataAnalysisRequest(sql_query="select * from deals"))


@pytest.mark.anyio
async def test_data_analyzer_uses_llm_summary_when_configured() -> None:
    model = _MockCompleter()
    analyzer = DataAnalyzer()
    await analyzer.initialize({"model_client": model, "force_llm": True})
    report = await analyzer.execute(DataAnalysisRequest(rows=[{"revenue": 5}, {"revenue": 7}]))
    assert report.narrative_summary.startswith("LLM summary:")
    assert model.calls == 1
