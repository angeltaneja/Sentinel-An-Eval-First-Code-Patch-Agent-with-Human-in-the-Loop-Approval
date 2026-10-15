"""
EVALUATE Node: Calculates comprehensive quality score card (pass rate, diff size, lint, files).
"""

import time
from typing import Any

from sentinel.evaluation.evaluator import PatchEvaluator
from sentinel.observability.structured_logger import logger
from sentinel.state import SandboxResult, SentinelState


def evaluate_node(state: SentinelState) -> dict[str, Any]:
    """Execute quantitative evaluation on the successful patch."""
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    repo_path = state.get("repo_path", ".")
    patch_diff = state.get("current_patch", "")
    sandbox_data = state.get("sandbox_result")

    sandbox_result = SandboxResult(**sandbox_data) if sandbox_data else None

    logger.info(f"[EVALUATE] Computing quality scorecard for issue #{issue_number}")

    eval_report = PatchEvaluator.evaluate(
        repo_path=repo_path,
        patch_diff=patch_diff,
        sandbox_result=sandbox_result,
    )

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition(
        "SANDBOX",
        "EVALUATE",
        str(issue_number),
        duration_ms,
        {
            "overall_score": eval_report.overall_score,
            "blast_loc": eval_report.loc_added + eval_report.loc_deleted,
            "lint_passed": eval_report.lint_passed,
        },
    )

    return {
        "eval_report": eval_report.model_dump(),
        "status": "evaluated",
    }
