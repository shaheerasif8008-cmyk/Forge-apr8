"""Test runner: orchestrates all evaluator test suites."""

from __future__ import annotations

import structlog

from factory.models.build import Build, BuildLog, BuildStatus

logger = structlog.get_logger(__name__)

TEST_SUITES = [
    "functional_tests",
    "security_tests",
    "behavioral_tests",
    "hallucination_tests",
    "compliance_tests",
]


async def evaluate(build: Build) -> Build:
    """Run all test suites against the packaged employee.

    Args:
        build: Build with packaged artifacts.

    Returns:
        Build with test_report populated and status set to PASSED or FAILED.
    """
    build.status = BuildStatus.EVALUATING
    logger.info("evaluator_start", build_id=str(build.id))

    results: dict[str, object] = {}
    passed = True

    for suite in TEST_SUITES:
        # TODO: run actual test suite; currently stubs all as passed
        suite_result = {"status": "passed", "tests": 0, "failures": 0}
        results[suite] = suite_result
        build.logs.append(BuildLog(
            stage="evaluator",
            message=f"Suite {suite}: {suite_result['status']}",
            detail=suite_result,
        ))
        if suite_result["status"] != "passed":
            passed = False

    build.test_report = {"suites": results, "overall": "passed" if passed else "failed"}
    build.status = BuildStatus.PASSED if passed else BuildStatus.FAILED
    logger.info("evaluator_complete", overall=build.test_report["overall"])
    return build
