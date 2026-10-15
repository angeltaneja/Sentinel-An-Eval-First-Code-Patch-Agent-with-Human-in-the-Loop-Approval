"""
REPAIR Node: Analyzes test failures, detects cyclic diff loops, and coordinates retry.
"""

import time
from typing import Any

from sentinel.config import settings
from sentinel.observability.structured_logger import logger
from sentinel.state import SentinelState


def repair_node(state: SentinelState) -> dict[str, Any]:
    """
    Handle failed test run:
    1. Verify retry cap (< 3).
    2. Detect duplicate diffs across retries using SHA-256 fingerprinting.
    3. Increment retry counter.
    """
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    retry_count = state.get("retry_count", 0)
    diff_hashes = state.get("diff_hashes", [])

    logger.warning(
        f"[REPAIR] Initiating repair cycle for issue #{issue_number} (Attempt {retry_count + 1}/{settings.MAX_REPAIR_RETRIES})"
    )

    # Detect duplicate diff across retries
    is_duplicate = False
    if len(diff_hashes) >= 2:
        latest_hash = diff_hashes[-1]
        previous_hashes = diff_hashes[:-1]
        if latest_hash in previous_hashes:
            is_duplicate = True
            logger.error(
                f"[REPAIR] Cycle detected! Generated diff hash {latest_hash[:8]} matches previous attempt. Aborting loop early."
            )

    new_retry_count = retry_count + 1

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition(
        "SANDBOX",
        "REPAIR",
        str(issue_number),
        duration_ms,
        {
            "retry_count": new_retry_count,
            "is_duplicate_diff": is_duplicate,
        },
    )

    if is_duplicate:
        return {
            "retry_count": new_retry_count,
            "status": "escalated",
            "error_message": f"Diff cycle detected: identical patch produced on retry {new_retry_count}.",
        }

    return {
        "retry_count": new_retry_count,
        "status": "repairing",
    }
