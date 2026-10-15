"""
SANDBOX Node: Validates the generated patch inside an isolated sandbox by executing repo tests.
"""

import time
from typing import Any

from sentinel.observability.structured_logger import logger
from sentinel.sandbox.factory import get_sandbox_runner
from sentinel.state import SandboxResult, SentinelState


def sandbox_node(state: SentinelState) -> dict[str, Any]:
    """Execute patch inside the isolated sandbox."""
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    repo_path = state.get("repo_path", ".")
    patch_diff = state.get("current_patch", "")
    plan = state.get("plan") or {}
    test_targets = plan.get("test_targets")

    logger.info(f"[SANDBOX] Launching isolated sandbox execution for issue #{issue_number}")

    runner = get_sandbox_runner()
    exec_result = runner.run_patch_and_tests(
        repo_path=repo_path,
        patch_diff=patch_diff,
        test_commands=test_targets,
    )

    result_obj = SandboxResult(
        patch_applied=exec_result.patch_applied,
        tests_passed=exec_result.tests_passed,
        exit_code=exec_result.exit_code,
        stdout=exec_result.stdout,
        stderr=exec_result.stderr,
        duration_seconds=exec_result.duration_seconds,
        failed_test_names=exec_result.failed_test_names,
        failure_traceback=exec_result.failure_traceback,
    )

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition(
        "GENERATE",
        "SANDBOX",
        str(issue_number),
        duration_ms,
        {
            "patch_applied": result_obj.patch_applied,
            "tests_passed": result_obj.tests_passed,
            "exit_code": result_obj.exit_code,
            "failed_tests": len(result_obj.failed_test_names),
        },
    )

    return {
        "sandbox_result": result_obj.model_dump(),
        "status": "sandboxed",
    }
