"""data_analyzer work capability component."""

from __future__ import annotations

import csv
import math
import os
from io import StringIO
from statistics import mean
from typing import Any

import structlog
from pydantic import BaseModel

from component_library.interfaces import ComponentHealth, WorkCapability
from component_library.models.litellm_router import TaskType
from component_library.registry import register
from component_library.work.schemas import (
    DataAnalysisRequest,
    DataColumnProfile,
    DataReport,
)

logger = structlog.get_logger(__name__)


@register("data_analyzer")
class DataAnalyzer(WorkCapability):
    config_schema = {
        "model_client": {"type": "object", "required": False, "description": "Optional model client for LLM-backed summaries.", "default": None},
        "query_runner": {"type": "object", "required": False, "description": "Optional callable/query runner for external structured data.", "default": None},
        "fallback_mode": {"type": "str", "required": False, "description": "Fallback analysis mode when no model client is used.", "default": "deterministic"},
        "force_llm": {"type": "bool", "required": False, "description": "Force LLM summary generation when a model client is configured.", "default": False},
    }
    component_id = "data_analyzer"
    version = "1.0.0"

    async def initialize(self, config: dict[str, Any]) -> None:
        self._config = config
        self._model_client = config.get("model_client")
        self._query_runner = config.get("query_runner")
        self._fallback_mode = str(config.get("fallback_mode", "deterministic"))

    async def health_check(self) -> ComponentHealth:
        mode = "llm_backed" if self._model_client is not None else "deterministic_fallback"
        query_runner = "configured" if self._query_runner is not None else "absent"
        return ComponentHealth(healthy=True, detail=f"mode={mode}; query_runner={query_runner}")

    def get_test_suite(self) -> list[str]:
        return ["tests/components/work/test_data_analyzer.py"]

    async def execute(self, input_data: BaseModel) -> BaseModel:
        if not isinstance(input_data, DataAnalysisRequest):
            raise TypeError("DataAnalyzer expects DataAnalysisRequest")
        return await self.analyze(input_data)

    async def analyze(self, request: DataAnalysisRequest) -> DataReport:
        rows = await self._load_rows(request)
        if not rows:
            return DataReport(
                schema=[],
                key_metrics={"row_count": 0, "column_count": 0},
                anomalies=[],
                narrative_summary="No tabular data was provided for analysis.",
            )

        schema = self._infer_schema(rows)
        metrics = self._compute_metrics(rows, schema)
        anomalies = self._detect_anomalies(rows, schema, request.max_anomalies)

        if self._can_use_model():
            try:
                narrative = await self._summarize_with_model(request, schema, metrics, anomalies)
            except Exception as exc:
                logger.warning("data_analyzer_llm_failed", error=str(exc))
                if self._fallback_mode != "deterministic":
                    raise
                narrative = self._build_narrative(request, schema, metrics, anomalies)
        else:
            narrative = self._build_narrative(request, schema, metrics, anomalies)

        return DataReport(
            schema=schema,
            key_metrics=metrics,
            anomalies=anomalies,
            narrative_summary=narrative,
        )

    async def _load_rows(self, request: DataAnalysisRequest) -> list[dict[str, Any]]:
        if request.rows:
            return [dict(row) for row in request.rows]
        if request.csv_data:
            reader = csv.DictReader(StringIO(request.csv_data.strip()))
            return [dict(row) for row in reader]
        if request.sql_query:
            if self._query_runner is None:
                raise ValueError("sql_query provided but no query_runner configured")
            result = self._query_runner(request.sql_query)
            if hasattr(result, "__await__"):
                result = await result
            return [dict(row) for row in result]
        return []

    def _infer_schema(self, rows: list[dict[str, Any]]) -> list[DataColumnProfile]:
        columns = sorted({key for row in rows for key in row.keys()})
        schema: list[DataColumnProfile] = []
        for column in columns:
            values = [row.get(column) for row in rows]
            null_count = sum(value in (None, "") for value in values)
            non_null_values = [value for value in values if value not in (None, "")]
            inferred_type = self._infer_column_type(non_null_values)
            unique_values = len({str(value) for value in non_null_values})
            schema.append(
                DataColumnProfile(
                    name=column,
                    inferred_type=inferred_type,
                    null_count=null_count,
                    unique_values=unique_values,
                )
            )
        return schema

    def _infer_column_type(self, values: list[Any]) -> str:
        if not values:
            return "empty"
        if all(self._coerce_float(value) is not None for value in values):
            return "numeric"
        if all(str(value).lower() in {"true", "false"} for value in values):
            return "boolean"
        return "string"

    def _compute_metrics(
        self,
        rows: list[dict[str, Any]],
        schema: list[DataColumnProfile],
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "row_count": len(rows),
            "column_count": len(schema),
        }
        for column in schema:
            if column.inferred_type != "numeric":
                continue
            values = [
                self._coerce_float(row.get(column.name))
                for row in rows
                if self._coerce_float(row.get(column.name)) is not None
            ]
            if not values:
                continue
            metrics[column.name] = {
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "mean": round(mean(values), 2),
                "sum": round(sum(values), 2),
            }
        return metrics

    def _detect_anomalies(
        self,
        rows: list[dict[str, Any]],
        schema: list[DataColumnProfile],
        max_anomalies: int,
    ) -> list[str]:
        anomalies: list[str] = []
        for column in schema:
            if column.inferred_type != "numeric":
                continue
            indexed_values = [
                (index, self._coerce_float(row.get(column.name)))
                for index, row in enumerate(rows)
            ]
            numeric_values = [value for _, value in indexed_values if value is not None]
            if len(numeric_values) < 3:
                continue
            average = mean(numeric_values)
            variance = mean([(value - average) ** 2 for value in numeric_values])
            deviation = math.sqrt(variance)
            if deviation == 0:
                continue
            for index, value in indexed_values:
                if value is None:
                    continue
                z_score = abs(value - average) / deviation
                if z_score >= 1.3:
                    anomalies.append(
                        f"Row {index + 1} column '{column.name}' is an outlier at {value:.2f} (z={z_score:.2f})."
                    )
                    if len(anomalies) >= max_anomalies:
                        return anomalies
        return anomalies

    def _build_narrative(
        self,
        request: DataAnalysisRequest,
        schema: list[DataColumnProfile],
        metrics: dict[str, Any],
        anomalies: list[str],
    ) -> str:
        numeric_columns = [column.name for column in schema if column.inferred_type == "numeric"]
        question_suffix = f" The analysis focused on: {request.question.strip()}." if request.question.strip() else ""
        anomaly_text = anomalies[0] if anomalies else "No major anomalies were detected in the numeric columns."
        return (
            f"Analyzed {metrics.get('row_count', 0)} rows across {metrics.get('column_count', 0)} columns. "
            f"Numeric columns: {', '.join(numeric_columns) if numeric_columns else 'none'}. "
            f"{anomaly_text}{question_suffix}"
        )

    async def _summarize_with_model(
        self,
        request: DataAnalysisRequest,
        schema: list[DataColumnProfile],
        metrics: dict[str, Any],
        anomalies: list[str],
    ) -> str:
        system_prompt = (
            "You are a business data analyst. Summarize the provided dataset metrics, highlight anomalies, "
            "and answer the user's question in 3 short sentences."
        )
        user_message = (
            f"QUESTION: {request.question or 'Summarize the dataset.'}\n"
            f"SCHEMA: {[column.model_dump(mode='json') for column in schema]}\n"
            f"KEY METRICS: {metrics}\n"
            f"ANOMALIES: {anomalies}"
        )
        if getattr(self._model_client, "component_id", "") == "litellm_router":
            return await self._model_client.complete(
                user_message,
                task_type=TaskType.REASONING,
                system_prompt=system_prompt,
            )
        if hasattr(self._model_client, "complete"):
            return await self._model_client.complete(system_prompt, user_message)
        return await self._model_client.complete(
            [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
        )

    def _can_use_model(self) -> bool:
        if self._model_client is None:
            return False
        if self._config.get("force_llm"):
            return True
        client_id = getattr(self._model_client, "component_id", "")
        if client_id == "litellm_router":
            return any(
                os.getenv(name)
                for name in ("OPENROUTER_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")
            )
        if client_id == "anthropic_provider":
            return bool(getattr(self._model_client, "_api_key", None) or os.getenv("ANTHROPIC_API_KEY"))
        return True

    def _coerce_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
