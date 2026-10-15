"""
RETRIEVE Node: AST-aware chunking and hybrid retrieval (BM25 + Dense + RRF).
"""

import time
from typing import Any

from sentinel.config import settings
from sentinel.observability.structured_logger import logger
from sentinel.retrieval.indexer import CodebaseIndexer
from sentinel.state import SentinelState


def retrieve_node(state: SentinelState) -> dict[str, Any]:
    """Index codebase using AST-aware chunker and retrieve most relevant code contexts."""
    start_time = time.time()
    issue_number = state.get("issue_number", 0)
    repo_path = state.get("repo_path", ".")
    plan = state.get("plan") or {}

    logger.info(f"[RETRIEVE] Indexing and retrieving context for issue #{issue_number}")

    # Build indexer and index repository
    indexer = CodebaseIndexer(repo_path)
    retriever = indexer.index()

    # Formulate query from issue description and plan
    query_parts: list[str] = [
        state.get("issue_title", ""),
        state.get("issue_body", "")[:500],
        plan.get("analysis", ""),
        " ".join(plan.get("candidate_files", [])),
    ]
    query = " ".join(p for p in query_parts if p).strip()

    # Execute hybrid search with Reciprocal Rank Fusion
    top_chunks = retriever.search(query=query, top_k=settings.TOP_K_CHUNKS)
    serialized_chunks = [chunk.model_dump() for chunk in top_chunks]

    duration_ms = (time.time() - start_time) * 1000
    logger.log_transition(
        "PLAN",
        "RETRIEVE",
        str(issue_number),
        duration_ms,
        {"retrieved_count": len(serialized_chunks)},
    )

    return {
        "retrieved_chunks": serialized_chunks,
        "status": "retrieved",
    }
