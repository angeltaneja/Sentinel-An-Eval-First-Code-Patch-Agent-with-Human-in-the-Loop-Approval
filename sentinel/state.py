"""
Sentinel State Schema.
Represents the state passed across LangGraph nodes, serialized into checkpoints.
"""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """AST/semantic code chunk retrieved for context."""
    file_path: str
    symbol_name: str | None = None
    node_type: str | None = None
    start_line: int
    end_line: int
    content: str
    bm25_score: float = 0.0
    dense_score: float = 0.0
    combined_score: float = 0.0


class PlanOutput(BaseModel):
    """Structured plan produced by the PLAN node."""
    analysis: str = Field(description="Summary of the root cause or requirement")
    candidate_files: list[str] = Field(description="Files that likely require edits")
    strategy: str = Field(description="Step-by-step patch implementation strategy")
    test_targets: list[str] = Field(description="Test commands or test files to validate the fix")


class SandboxResult(BaseModel):
    """Output from executing the patch inside the isolated sandbox."""
    patch_applied: bool = Field(description="Whether git apply succeeded")
    tests_passed: bool = Field(description="Whether test suite returned exit code 0")
    exit_code: int = Field(default=0)
    stdout: str = Field(default="")
    stderr: str = Field(default="")
    duration_seconds: float = Field(default=0.0)
    failed_test_names: list[str] = Field(default_factory=list)
    failure_traceback: str | None = None


class EvalReport(BaseModel):
    """Evaluation score card computed in EVALUATE node."""
    test_pass_rate: float = Field(default=0.0, description="Percentage of passed tests (0.0 to 1.0)")
    loc_added: int = Field(default=0)
    loc_deleted: int = Field(default=0)
    files_touched: list[str] = Field(default_factory=list)
    lint_passed: bool = Field(default=True)
    lint_violations: list[str] = Field(default_factory=list)
    syntax_valid: bool = Field(default=True)
    overall_score: float = Field(default=0.0, description="Weighted composite score")
    summary: str = Field(default="")


class HumanApproval(BaseModel):
    """Approval payload provided at the human gate."""
    approved: bool
    reviewer: str = Field(default="system_human")
    feedback: str | None = None
    timestamp: str | None = None


class SentinelState(TypedDict, total=False):
    """Complete LangGraph state machine payload."""

    # Target Repository & Issue Metadata
    repo_name: str
    repo_path: str
    issue_number: int
    issue_title: str
    issue_body: str
    issue_author: str
    issue_comments: list[dict[str, Any]]

    # Planning
    plan: dict[str, Any] | None

    # Retrieval
    retrieved_chunks: list[dict[str, Any]]

    # Patch Generation & Repair Loop
    current_patch: str | None
    diff_history: list[str]
    diff_hashes: list[str]
    retry_count: int

    # Sandbox & Verification
    sandbox_result: dict[str, Any] | None

    # Evaluation
    eval_report: dict[str, Any] | None

    # Human Gate
    human_approval: dict[str, Any] | None

    # Final Commit / PR Action
    pr_result: dict[str, Any] | None

    # Observability & Lifecycle
    status: Literal[
        "initialized",
        "ingested",
        "planned",
        "retrieved",
        "generated",
        "sandboxed",
        "repairing",
        "escalated",
        "evaluated",
        "awaiting_approval",
        "approved",
        "rejected",
        "committed",
        "failed",
    ]
    error_message: str | None
    transition_logs: list[dict[str, Any]]
