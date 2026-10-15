"""
ESCALATE Node: Handles bounded retry exhaustion or cyclic failure and logs incident post-mortem.
"""

import time
from typing import Any

from sentinel.observability.structured_logger import logger
from sentinel.state import SentinelState


def escalate_node(state: SentinelState) -> dict[str, Any]:
    """Escalate repair exhaustion or cycle detection to engineering alert."""
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    retry_count = state.get("retry_count", 0)
    sandbox_result = state.get("sandbox_result") or {}
    error_msg = state.get("error_message") or "Max repair retries (3) exhausted without passing tests."

    logger.error(
        f"[ESCALATE] Patch generation for issue #{issue_number} ESCALATED! Reason: {error_msg}"
    )

    incident_report = {
        "issue_number": issue_number,
        "retries_attempted": retry_count,
        "failed_tests": sandbox_result.get("failed_test_names", []),
        "exit_code": sandbox_result.get("exit_code"),
        "error_message": error_msg,
    }

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition(
        "REPAIR/SANDBOX",
        "ESCALATE",
        str(issue_number),
        duration_ms,
        incident_report,
    )

    return {
        "status": "escalated",
        "error_message": error_msg,
    }
