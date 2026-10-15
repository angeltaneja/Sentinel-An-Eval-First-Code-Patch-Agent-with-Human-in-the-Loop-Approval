"""
Integration tests for the LangGraph State Machine.
Verifies the non-linear topology, Human Approval Gate interrupt, and state resumption.
"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from sentinel.graph import build_sentinel_graph, route_after_sandbox
from sentinel.state import SentinelState


def test_route_after_sandbox_logic():
    # 1. Tests passed -> evaluate
    state_pass: SentinelState = {
        "sandbox_result": {"tests_passed": True, "exit_code": 0},
        "retry_count": 0,
    }
    assert route_after_sandbox(state_pass) == "evaluate"

    # 2. Tests failed and retries < 3 -> repair
    state_fail: SentinelState = {
        "sandbox_result": {"tests_passed": False, "exit_code": 1},
        "retry_count": 1,
    }
    assert route_after_sandbox(state_fail) == "repair"

    # 3. Tests failed and retries >= 3 -> escalate
    state_exhausted: SentinelState = {
        "sandbox_result": {"tests_passed": False, "exit_code": 1},
        "retry_count": 3,
    }
    assert route_after_sandbox(state_exhausted) == "escalate"


def test_graph_pauses_at_human_gate_and_resumes_on_approval(monkeypatch):
    """
    Simulate full graph run:
    - Should pause at human_gate via interrupt()
    - When resumed with {'approved': True}, transitions to commit and terminates.
    """
    # Mock sandbox node before graph compilation to return tests_passed=True
    def mock_sandbox(state: SentinelState):
        return {
            "sandbox_result": {
                "patch_applied": True,
                "tests_passed": True,
                "exit_code": 0,
                "stdout": "1 passed",
                "stderr": "",
                "duration_seconds": 0.5,
                "failed_test_names": [],
            },
            "status": "sandboxed",
        }

    monkeypatch.setattr("sentinel.nodes.sandbox.sandbox_node", mock_sandbox)
    monkeypatch.setattr("sentinel.graph.sandbox_node", mock_sandbox)

    checkpointer = MemorySaver()
    graph = build_sentinel_graph(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "test-thread-approval-001"}}
    initial_state = {
        "repo_name": "sentinel/test-repo",
        "repo_path": ".",
        "issue_number": 101,
        "issue_title": "Fix division by zero",
        "issue_body": "ZeroDivisionError in calculate_ratio",
    }

    # Run graph until interrupt
    events = list(graph.stream(initial_state, config=config, stream_mode="updates"))
    assert len(events) > 0

    # Verify graph paused at human_gate
    snapshot = graph.get_state(config)
    assert snapshot.next == ("human_gate",)
    assert snapshot.values["status"] == "evaluated"
    assert "eval_report" in snapshot.values

    # Resume graph with explicit Human Approval
    approval_payload = {
        "approved": True,
        "reviewer": "senior_ml_eng",
        "feedback": "LGTM, blast radius is minimal.",
    }

    resume_events = list(
        graph.stream(Command(resume=approval_payload), config=config, stream_mode="updates")
    )
    assert len(resume_events) > 0

    final_snapshot = graph.get_state(config)
    assert final_snapshot.next == ()  # Reached END
    assert final_snapshot.values["status"] == "committed"
    assert final_snapshot.values["human_approval"]["approved"] is True
    assert final_snapshot.values["pr_result"]["status"] == "draft_opened"


def test_graph_terminates_on_human_rejection(monkeypatch):
    """
    Simulate full graph run:
    - Resumes with {'approved': False}
    - Transitions to END without commit.
    """
    def mock_sandbox(state: SentinelState):
        return {
            "sandbox_result": {
                "patch_applied": True,
                "tests_passed": True,
                "exit_code": 0,
                "stdout": "1 passed",
                "stderr": "",
                "duration_seconds": 0.5,
                "failed_test_names": [],
            },
            "status": "sandboxed",
        }

    monkeypatch.setattr("sentinel.nodes.sandbox.sandbox_node", mock_sandbox)
    monkeypatch.setattr("sentinel.graph.sandbox_node", mock_sandbox)

    checkpointer = MemorySaver()
    graph = build_sentinel_graph(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": "test-thread-rejection-002"}}
    initial_state = {
        "repo_name": "sentinel/test-repo",
        "repo_path": ".",
        "issue_number": 102,
        "issue_title": "Fix typo",
        "issue_body": "Typo in readme",
    }

    # Run until interrupt
    list(graph.stream(initial_state, config=config, stream_mode="updates"))

    # Resume with Rejection
    rejection_payload = {
        "approved": False,
        "reviewer": "lead_maintainer",
        "feedback": "Needs rework on edge cases.",
    }

    list(graph.stream(Command(resume=rejection_payload), config=config, stream_mode="updates"))

    final_snapshot = graph.get_state(config)
    assert final_snapshot.next == ()  # Reached END without commit
    assert final_snapshot.values["status"] == "rejected"
    assert final_snapshot.values["human_approval"]["approved"] is False
