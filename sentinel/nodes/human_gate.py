"""
HUMAN GATE Node: Pauses execution via LangGraph interrupt() and renders diff + eval report.
Resumes upon explicit human approval or rejection.
"""

import time
from typing import Any

from langgraph.types import interrupt

from sentinel.observability.structured_logger import logger
from sentinel.state import HumanApproval, SentinelState


def human_gate_node(state: SentinelState) -> dict[str, Any]:
    """
    Pause execution at the Human Approval Gate using LangGraph's interrupt().
    Persists state in checkpointer until human resumes with approval decision.
    """
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    current_patch = state.get("current_patch", "")
    eval_report = state.get("eval_report") or {}

    logger.info(f"[HUMAN_GATE] Pausing graph execution at Human Approval Gate for issue #{issue_number}")

    # Prepare review payload presented to reviewer
    review_package = {
        "issue_number": issue_number,
        "issue_title": state.get("issue_title"),
        "eval_report": eval_report,
        "patch_diff": current_patch,
        "prompt": "Review the patch diff and evaluation scorecard. Provide {'approved': true/false, 'reviewer': '...', 'feedback': '...'}",
    }

    # LangGraph interrupt: Pauses graph execution and serializes state to checkpointer
    human_response = interrupt(review_package)

    # When graph is resumed, execution continues here with human_response
    if isinstance(human_response, dict):
        approval = HumanApproval(
            approved=bool(human_response.get("approved", False)),
            reviewer=str(human_response.get("reviewer", "human_reviewer")),
            feedback=human_response.get("feedback"),
            timestamp=str(time.time()),
        )
    elif isinstance(human_response, bool):
        approval = HumanApproval(
            approved=human_response,
            reviewer="human_reviewer",
            timestamp=str(time.time()),
        )
    else:
        approval = HumanApproval(
            approved=False,
            reviewer="system",
            feedback=f"Unrecognized response format: {human_response}",
            timestamp=str(time.time()),
        )

    duration_ms = (time.time() - start_time) * 1000
    decision = "APPROVED" if approval.approved else "REJECTED"
    logger.log_transition(
        "EVALUATE",
        "HUMAN_GATE",
        str(issue_number),
        duration_ms,
        {"decision": decision, "reviewer": approval.reviewer, "feedback": approval.feedback},
    )

    return {
        "human_approval": approval.model_dump(),
        "status": "approved" if approval.approved else "rejected",
    }
