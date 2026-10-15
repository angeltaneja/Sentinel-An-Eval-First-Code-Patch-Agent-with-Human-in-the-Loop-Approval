"""
Unit tests for Repair Loop Bounding and Diff Cycle Detection.
"""

import hashlib

from sentinel.nodes.repair import repair_node
from sentinel.state import SentinelState


def test_diff_cycle_detector_breaks_on_duplicate_diff():
    diff1 = """--- a/main.py
+++ b/main.py
@@ -1,2 +1,2 @@
-print('old')
+print('new')
"""
    hash1 = hashlib.sha256(diff1.encode("utf-8")).hexdigest()

    # State with duplicate diff hash on retry 2
    state: SentinelState = {
        "issue_number": 42,
        "retry_count": 1,
        "diff_history": [diff1, diff1],
        "diff_hashes": [hash1, hash1],  # Identical hash repeated!
        "sandbox_result": {"tests_passed": False, "exit_code": 1},
    }

    result = repair_node(state)

    # Must break early and mark status as escalated
    assert result["status"] == "escalated"
    assert "Diff cycle detected" in result["error_message"]
    assert result["retry_count"] == 2


def test_repair_increments_retry_on_distinct_diff():
    diff1 = "diff 1"
    diff2 = "diff 2"
    hash1 = hashlib.sha256(diff1.encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(diff2.encode("utf-8")).hexdigest()

    state: SentinelState = {
        "issue_number": 42,
        "retry_count": 0,
        "diff_history": [diff1, diff2],
        "diff_hashes": [hash1, hash2],
        "sandbox_result": {"tests_passed": False, "exit_code": 1},
    }

    result = repair_node(state)

    assert result["status"] == "repairing"
    assert result["retry_count"] == 1
    assert "error_message" not in result
