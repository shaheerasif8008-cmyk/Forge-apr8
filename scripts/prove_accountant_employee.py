#!/usr/bin/env python3
"""Commission and evaluate a Forge AI Accountant employee."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import prove_server_export as proof

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from factory.commissioning.fixtures import load_requirements_fixture
from factory.pipeline.evaluator.accountant_tests import load_accountant_cases, score_accountant_answer


def _commission_accountant(ctx: proof.ProofContext) -> None:
    requirements = load_requirements_fixture("accountant", org_id=proof.DEFAULT_ORG_ID)
    status, payload = proof._request_json(
        "POST",
        f"{ctx.api_base}/commissions",
        headers={"Authorization": f"Bearer {ctx.auth_token}"},
        payload=requirements.model_dump(mode="json"),
    )
    if status != 202 or not payload.get("build_id"):
        raise RuntimeError(f"Commission request failed: HTTP {status} {payload}")
    ctx.build_id = str(payload["build_id"])
    ctx.record("accountant_commission", status_code=status, build_id=ctx.build_id)


def main() -> int:
    ctx = proof.ProofContext(
        api_base=proof.DEFAULT_API,
        factory_env=proof._merged_env(),
        employee_env=proof._merged_env(),
    )
    if not proof._preflight(ctx):
        print(proof._report(ctx))
        return 2

    proof._start_stack(ctx)
    proof._ensure_proof_org(ctx)
    proof._issue_factory_token(ctx)
    _commission_accountant(ctx)
    build = proof._wait_for_build(ctx)
    bundle_dir = proof._extract_bundle(ctx, build, "")
    proof._write_bundle_env(ctx, bundle_dir)
    proof._start_employee_bundle(ctx, bundle_dir)

    scores = []
    task = {}
    brief = {}
    for case in load_accountant_cases():
        task_id = proof._submit_task(ctx, case["input"])
        task = proof._wait_for_task(ctx, task_id)
        brief = proof._get_brief(ctx, task_id)
        answer = json.dumps(brief, indent=2, sort_keys=True)
        score = score_accountant_answer(answer, case)
        scores.append(score)
        ctx.record("accountant_eval_case", case_id=case["id"], task_id=task_id, task_status=task.get("status"), score=score)

    proof._stop_factory_stack()
    time.sleep(2)
    second_task_id = proof._submit_task(
        ctx,
        "Under ASC 606, list the five revenue recognition steps in order.",
    )
    second_task = proof._wait_for_task(ctx, second_task_id)
    second_brief = proof._get_brief(ctx, second_task_id)
    ctx.record(
        "sovereignty_second_task",
        task_id=second_task_id,
        task_status=second_task.get("status"),
        answer_preview=str(second_brief)[:500],
    )

    report = {
        **json.loads(proof._report(ctx)),
        "accountant_task": task,
        "accountant_brief": brief,
        "accountant_scores": scores,
        "sovereignty_second_task": second_task,
        "sovereignty_second_brief": second_brief,
    }
    artifact = Path("artifacts/accountant_factory_run.json")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
