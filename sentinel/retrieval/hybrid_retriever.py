"""
AST-Aware Hybrid Search (BM25 Lexical + Dense Embeddings + Reciprocal Rank Fusion).
Combines exact identifier matching with semantic intent retrieval.
"""

import re

import numpy as np
from rank_bm25 import BM25Okapi

from sentinel.config import settings
from sentinel.observability.structured_logger import logger
from sentinel.retrieval.ast_chunker import CodeChunk
from sentinel.state import RetrievedChunk


def tokenize_code(text: str) -> list[str]:
    """Tokenize code preserving symbols, snake_case, camelCase, and dotted identifiers."""
    # Split on whitespace and non-alphanumeric chars while keeping subwords
    raw_tokens = re.findall(r"[A-Za-z0-9_]+", text)
    tokens: list[str] = []
    for token in raw_tokens:
        tokens.append(token.lower())
        # CamelCase splitting: MyClass -> my, class
        sub_tokens = re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\d|\W|$)|\d+", token)
        if len(sub_tokens) > 1:
            for sub in sub_tokens:
                tokens.append(sub.lower())
        # snake_case splitting
        if "_" in token:
            for part in token.split("_"):
                if part:
                    tokens.append(part.lower())
    return tokens


class HybridRetriever:
    """Hybrid code search combining BM25 lexical ranking and dense semantic similarity via RRF."""

    def __init__(self, rrf_k: int = 60):
        self.rrf_k = rrf_k
        self.chunks: list[CodeChunk] = []
        self.bm25_index: BM25Okapi | None = None
        self.dense_vectors: np.ndarray | None = None
        self._openai_client = None

        if settings.OPENAI_API_KEY:
            try:
                from langchain_openai import OpenAIEmbeddings

                self._openai_client = OpenAIEmbeddings(
                    model=settings.EMBEDDING_MODEL,
                    api_key=settings.OPENAI_API_KEY,
                )
            except Exception as e:
                logger.warning(f"Could not initialize OpenAIEmbeddings: {e}")

    def index_chunks(self, chunks: list[CodeChunk]) -> None:
        """Build BM25 and dense representation indices over chunks."""
        self.chunks = chunks
        if not chunks:
            self.bm25_index = None
            self.dense_vectors = None
            return

        # 1. Build BM25 index
        corpus_tokens = [tokenize_code(f"{c.file_path} {c.symbol_name or ''}\n{c.content}") for c in chunks]
        self.bm25_index = BM25Okapi(corpus_tokens)

        # 2. Build Dense Vectors
        texts_to_embed = [
            f"File: {c.file_path} | Symbol: {c.symbol_name or 'N/A'}\n{c.content[:1000]}"
            for c in chunks
        ]

        if self._openai_client:
            try:
                vectors = self._openai_client.embed_documents(texts_to_embed)
                self.dense_vectors = np.array(vectors, dtype=np.float32)
                # Normalize for cosine similarity
                norms = np.linalg.norm(self.dense_vectors, axis=1, keepdims=True)
                norms[norms == 0] = 1e-10
                self.dense_vectors = self.dense_vectors / norms
                return
            except Exception as err:
                logger.warning(f"Embedding generation failed: {err}. Falling back to internal dense vectors.")

        # Internal lightweight dense fallback (TF-IDF weighted feature vector)
        self.dense_vectors = self._build_fallback_dense_vectors(corpus_tokens)

    def _build_fallback_dense_vectors(self, corpus_tokens: list[list[str]]) -> np.ndarray:
        """Create fallback normalized dense vectors based on sub-token frequency hashing."""
        vocab_size = 512
        vectors = np.zeros((len(corpus_tokens), vocab_size), dtype=np.float32)

        for i, tokens in enumerate(corpus_tokens):
            for t in tokens:
                idx = abs(hash(t)) % vocab_size
                vectors[i, idx] += 1.0

        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1e-10
        return vectors / norms

    def _embed_query_fallback(self, query: str) -> np.ndarray:
        """Embed search query with fallback feature hasher."""
        tokens = tokenize_code(query)
        vocab_size = 512
        vector = np.zeros((1, vocab_size), dtype=np.float32)
        for t in tokens:
            idx = abs(hash(t)) % vocab_size
            vector[0, idx] += 1.0
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        return vector

    def search(self, query: str, top_k: int = 8) -> list[RetrievedChunk]:
        """Perform hybrid search using Reciprocal Rank Fusion (RRF)."""
        if not self.chunks or self.bm25_index is None:
            return []

        query_tokens = tokenize_code(query)
        num_docs = len(self.chunks)

        # 1. Lexical BM25 Ranking
        bm25_raw_scores = self.bm25_index.get_scores(query_tokens)
        bm25_ranked_indices = np.argsort(bm25_raw_scores)[::-1]
        bm25_ranks: dict[int, int] = {idx: rank + 1 for rank, idx in enumerate(bm25_ranked_indices)}

        # 2. Dense Semantic Ranking
        if self._openai_client and self.dense_vectors is not None:
            try:
                q_vec = np.array(self._openai_client.embed_query(query), dtype=np.float32)
                q_norm = np.linalg.norm(q_vec)
                if q_norm > 0:
                    q_vec = q_vec / q_norm
                dense_scores = np.dot(self.dense_vectors, q_vec)
            except Exception:
                q_vec = self._embed_query_fallback(query)
                dense_scores = np.dot(self.dense_vectors, q_vec.T).flatten()
        else:
            q_vec = self._embed_query_fallback(query)
            dense_scores = np.dot(self.dense_vectors, q_vec.T).flatten()

        dense_ranked_indices = np.argsort(dense_scores)[::-1]
        dense_ranks: dict[int, int] = {idx: rank + 1 for rank, idx in enumerate(dense_ranked_indices)}

        # 3. Reciprocal Rank Fusion (RRF)
        # RRF_score(d) = 1/(k + rank_bm25(d)) + 1/(k + rank_dense(d))
        rrf_scores: list[tuple[int, float]] = []
        for idx in range(num_docs):
            r_bm25 = bm25_ranks.get(idx, num_docs + 1)
            r_dense = dense_ranks.get(idx, num_docs + 1)
            rrf_score = (1.0 / (self.rrf_k + r_bm25)) + (1.0 / (self.rrf_k + r_dense))
            rrf_scores.append((idx, rrf_score))

        # Sort by RRF score descending
        rrf_scores.sort(key=lambda x: x[1], reverse=True)
        top_results = rrf_scores[:top_k]

        results: list[RetrievedChunk] = []
        for idx, score in top_results:
            chunk = self.chunks[idx]
            results.append(
                RetrievedChunk(
                    file_path=chunk.file_path,
                    symbol_name=chunk.symbol_name,
                    node_type=chunk.node_type,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    bm25_score=float(bm25_raw_scores[idx]),
                    dense_score=float(dense_scores[idx]),
                    combined_score=float(score),
                )
            )

        return results
