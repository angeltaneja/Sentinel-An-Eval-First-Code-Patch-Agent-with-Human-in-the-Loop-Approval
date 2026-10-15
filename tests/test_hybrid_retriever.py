"""
Unit tests for AST-aware Hybrid Retriever (BM25 + Dense + RRF).
"""

from sentinel.retrieval.ast_chunker import CodeChunk
from sentinel.retrieval.hybrid_retriever import HybridRetriever, tokenize_code


def test_tokenize_code():
    tokens = tokenize_code("def calculate_retry_backoff(retryCount: int):")
    assert "calculate" in tokens
    assert "retry" in tokens
    assert "backoff" in tokens
    assert "calculate_retry_backoff" in tokens


def test_hybrid_retriever_ranking_exact_identifier():
    chunks = [
        CodeChunk(
            file_path="src/network.py",
            symbol_name="send_payload",
            node_type="function_definition",
            start_line=1,
            end_line=10,
            content="def send_payload(data):\n    pass",
        ),
        CodeChunk(
            file_path="src/retry.py",
            symbol_name="compute_backoff_delay",
            node_type="function_definition",
            start_line=1,
            end_line=15,
            content="def compute_backoff_delay(retry_attempt):\n    return 2 ** retry_attempt",
        ),
        CodeChunk(
            file_path="src/database.py",
            symbol_name="connect_db",
            node_type="function_definition",
            start_line=1,
            end_line=8,
            content="def connect_db():\n    pass",
        ),
    ]

    retriever = HybridRetriever(rrf_k=60)
    retriever.index_chunks(chunks)

    results = retriever.search("fix compute_backoff_delay retry issue", top_k=2)

    assert len(results) > 0
    # Top result should be retry.py due to exact identifier match
    assert results[0].file_path == "src/retry.py"
    assert results[0].symbol_name == "compute_backoff_delay"
    assert results[0].combined_score > 0.0
