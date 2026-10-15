"""
Sentinel LangGraph State Machine Architecture.
Explicitly constructs the cyclic, human-gated, eval-first state graph with persistent checkpointing.
"""


from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from sentinel.checkpointer import create_checkpointer
from sentinel.config import settings
from sentinel.nodes.commit import commit_node
from sentinel.nodes.escalate import escalate_node
from sentinel.nodes.evaluate import evaluate_node
from sentinel.nodes.generate import generate_node
from sentinel.nodes.human_gate import human_gate_node
from sentinel.nodes.ingest import ingest_node
from sentinel.nodes.plan import plan_node
from sentinel.nodes.repair import repair_node
from sentinel.nodes.retrieve import retrieve_node
from sentinel.nodes.sandbox import sandbox_node
from sentinel.state import SentinelState


def route_after_sandbox(state: SentinelState) -> str:
    """
    Evaluate sandbox test outcome:
    - If tests passed -> EVALUATE
    - If tests failed and retries < max -> REPAIR
    - If tests failed and retries >= max -> ESCALATE
    """
    sandbox_res = state.get("sandbox_result") or {}
    tests_passed = sandbox_res.get("tests_passed", False)
    retry_count = state.get("retry_count", 0)

    if tests_passed:
        return "evaluate"

    if retry_count < settings.MAX_REPAIR_RETRIES:
        return "repair"

    return "escalate"


def route_after_repair(state: SentinelState) -> str:
    """
    Route from repair node:
    - If cycle/identical diff was detected -> ESCALATE
    - Otherwise -> back to GENERATE
    """
    if state.get("status") == "escalated":
        return "escalate"
    return "generate"


def route_after_human_gate(state: SentinelState) -> str:
    """
    Route from human approval gate:
    - If explicitly approved by human -> COMMIT (open draft PR)
    - If rejected -> END (logged with reason)
    """
    approval = state.get("human_approval") or {}
    if approval.get("approved", False):
        return "commit"
    return END


def build_sentinel_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    """
    Assemble the complete Sentinel LangGraph state machine.
    Never flattens the graph into a linear chain.
    """
    workflow = StateGraph(SentinelState)

    # 1. Register Nodes
    workflow.add_node("ingest", ingest_node)
    workflow.add_node("plan", plan_node)
    workflow.add_node("retrieve", retrieve_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("sandbox", sandbox_node)
    workflow.add_node("repair", repair_node)
    workflow.add_node("escalate", escalate_node)
    workflow.add_node("evaluate", evaluate_node)
    workflow.add_node("human_gate", human_gate_node)
    workflow.add_node("commit", commit_node)

    # 2. Linear Pipeline Edges
    workflow.add_edge(START, "ingest")
    workflow.add_edge("ingest", "plan")
    workflow.add_edge("plan", "retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", "sandbox")

    # 3. Dynamic Bounded Repair Loop Routing
    workflow.add_conditional_edges(
        "sandbox",
        route_after_sandbox,
        {
            "evaluate": "evaluate",
            "repair": "repair",
            "escalate": "escalate",
        },
    )

    workflow.add_conditional_edges(
        "repair",
        route_after_repair,
        {
            "generate": "generate",
            "escalate": "escalate",
        },
    )

    # 4. Terminal Branches
    workflow.add_edge("escalate", END)
    workflow.add_edge("evaluate", "human_gate")

    # 5. Human-Gated Approval Routing
    workflow.add_conditional_edges(
        "human_gate",
        route_after_human_gate,
        {
            "commit": "commit",
            END: END,
        },
    )

    workflow.add_edge("commit", END)

    # 6. Checkpoint Persistence
    active_checkpointer = checkpointer if checkpointer is not None else create_checkpointer()

    return workflow.compile(
        checkpointer=active_checkpointer,
    )
