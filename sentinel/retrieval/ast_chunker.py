"""
AST-Aware Code Chunker using Tree-sitter.
Chunks source code at logical syntactic boundaries (functions, classes, methods)
rather than naive arbitrary line slices.
"""

from dataclasses import dataclass
from pathlib import Path

import tree_sitter

from sentinel.observability.structured_logger import logger


@dataclass
class CodeChunk:
    """Represents a syntactically coherent chunk of source code."""
    file_path: str
    symbol_name: str | None
    node_type: str
    start_line: int
    end_line: int
    content: str


class ASTChunker:
    """Extracts semantic code chunks using Tree-sitter AST parsers."""

    TARGET_NODE_TYPES = {
        "python": {
            "function_definition",
            "async_function_definition",
            "class_definition",
        },
        "javascript": {
            "function_declaration",
            "method_definition",
            "class_declaration",
            "arrow_function",
        },
    }

    def __init__(self):
        self._parsers: dict[str, tree_sitter.Parser] = {}
        self._init_languages()

    def _init_languages(self) -> None:
        """Initialize available tree-sitter language parsers."""
        try:
            import tree_sitter_python

            py_lang = tree_sitter.Language(tree_sitter_python.language())
            self._parsers["python"] = tree_sitter.Parser(py_lang)
        except Exception as e:
            logger.warning(f"Could not load tree-sitter python parser: {e}")

        try:
            import tree_sitter_javascript

            js_lang = tree_sitter.Language(tree_sitter_javascript.language())
            self._parsers["javascript"] = tree_sitter.Parser(js_lang)
        except Exception as e:
            logger.warning(f"Could not load tree-sitter javascript parser: {e}")

    def detect_language(self, file_path: str) -> str | None:
        """Map file extension to language identifier."""
        suffix = Path(file_path).suffix.lower()
        if suffix in [".py", ".pyw"]:
            return "python"
        elif suffix in [".js", ".jsx", ".mjs"]:
            return "javascript"
        return None

    def chunk_file(self, file_path: str, source_code: str) -> list[CodeChunk]:
        """Extract AST-aware chunks from a file with fallback to windowed chunking."""
        lang = self.detect_language(file_path)
        if not lang or lang not in self._parsers:
            return self._fallback_window_chunk(file_path, source_code)

        try:
            parser = self._parsers[lang]
            source_bytes = source_code.encode("utf-8")
            tree = parser.parse(source_bytes)
            chunks: list[CodeChunk] = []

            target_types = self.TARGET_NODE_TYPES.get(lang, set())

            def walk_node(node: tree_sitter.Node) -> None:
                if node.type in target_types:
                    symbol_name = self._extract_identifier(node)
                    chunk_text = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
                    
                    chunks.append(
                        CodeChunk(
                            file_path=file_path,
                            symbol_name=symbol_name,
                            node_type=node.type,
                            start_line=node.start_point.row + 1,
                            end_line=node.end_point.row + 1,
                            content=chunk_text,
                        )
                    )
                    # For classes, also traverse methods
                    if "class" in node.type:
                        for child in node.children:
                            walk_node(child)
                    return

                for child in node.children:
                    walk_node(child)

            walk_node(tree.root_node)

            # If no AST symbols found (e.g. script with only top-level statements), return file or windows
            if not chunks:
                return self._fallback_window_chunk(file_path, source_code)

            return chunks
        except Exception as err:
            logger.warning(f"AST parsing failed for {file_path}: {err}. Falling back to window chunker.")
            return self._fallback_window_chunk(file_path, source_code)

    def _extract_identifier(self, node: tree_sitter.Node) -> str | None:
        """Extract function or class name from AST node."""
        for child in node.children:
            if child.type in ("identifier", "name", "property_identifier"):
                return child.text.decode("utf-8", errors="replace")
        return None

    def _fallback_window_chunk(
        self, file_path: str, source_code: str, window_lines: int = 50, overlap_lines: int = 10
    ) -> list[CodeChunk]:
        """Sliding-window fallback chunker for unsupported languages or flat scripts."""
        lines = source_code.splitlines()
        if not lines:
            return []

        chunks: list[CodeChunk] = []
        step = max(1, window_lines - overlap_lines)

        for i in range(0, len(lines), step):
            window = lines[i : i + window_lines]
            chunk_content = "\n".join(window)
            chunks.append(
                CodeChunk(
                    file_path=file_path,
                    symbol_name=None,
                    node_type="line_window",
                    start_line=i + 1,
                    end_line=min(len(lines), i + len(window)),
                    content=chunk_content,
                )
            )
        return chunks
