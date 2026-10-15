"""
Codebase Indexer for Sentinel.
Walks target repository, chunks files with ASTChunker, and populates HybridRetriever.
"""

from pathlib import Path

from sentinel.observability.structured_logger import logger
from sentinel.retrieval.ast_chunker import ASTChunker, CodeChunk
from sentinel.retrieval.hybrid_retriever import HybridRetriever

DEFAULT_IGNORE_DIRS: set[str] = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "build",
    "dist",
    ".eggs",
}

DEFAULT_INCLUDED_EXTENSIONS: set[str] = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".json",
    ".toml",
    ".yaml",
    ".yml",
    ".md",
}


class CodebaseIndexer:
    """Recursively parses and indexes a repository for AST-aware hybrid retrieval."""

    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        self.chunker = ASTChunker()

    def index(self) -> HybridRetriever:
        """Scan codebase, extract semantic chunks, and build index."""
        logger.info(f"Indexing repository at {self.repo_path}...")
        all_chunks: list[CodeChunk] = []
        files_indexed = 0

        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Check ignore directories
            if any(part in DEFAULT_IGNORE_DIRS for part in file_path.parts):
                continue

            if file_path.suffix.lower() not in DEFAULT_INCLUDED_EXTENSIONS:
                continue

            # Skip large files (> 500 KB)
            try:
                if file_path.stat().st_size > 500 * 1024:
                    continue
                content = file_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                logger.warning(f"Failed to read file {file_path}: {e}")
                continue

            relative_path = str(file_path.relative_to(self.repo_path)).replace("\\", "/")
            chunks = self.chunker.chunk_file(relative_path, content)
            all_chunks.extend(chunks)
            files_indexed += 1

        logger.info(f"Indexed {files_indexed} files into {len(all_chunks)} semantic AST chunks.")
        retriever = HybridRetriever()
        retriever.index_chunks(all_chunks)
        return retriever
