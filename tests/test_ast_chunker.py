"""
Unit tests for Tree-sitter AST-Aware Code Chunker.
"""

from sentinel.retrieval.ast_chunker import ASTChunker


def test_ast_chunker_python_functions_and_classes():
    code = """
def calculate_metrics(values):
    \"\"\"Docstring\"\"\"
    return sum(values)

class RiskEvaluator:
    def __init__(self, threshold):
        self.threshold = threshold

    def evaluate(self, score):
        return score >= self.threshold
"""
    chunker = ASTChunker()
    chunks = chunker.chunk_file("src/evaluator.py", code)

    assert len(chunks) >= 3

    symbols = [c.symbol_name for c in chunks if c.symbol_name]
    assert "calculate_metrics" in symbols
    assert "RiskEvaluator" in symbols
    assert "evaluate" in symbols

    # Verify line numbers
    func_chunk = next(c for c in chunks if c.symbol_name == "calculate_metrics")
    assert func_chunk.start_line == 2
    assert "def calculate_metrics" in func_chunk.content


def test_ast_chunker_fallback_on_unsupported_language():
    code = "line1\nline2\nline3\nline4\nline5\n"
    chunker = ASTChunker()
    chunks = chunker.chunk_file("data.txt", code)

    assert len(chunks) >= 1
    assert chunks[0].node_type == "line_window"
    assert "line1" in chunks[0].content
