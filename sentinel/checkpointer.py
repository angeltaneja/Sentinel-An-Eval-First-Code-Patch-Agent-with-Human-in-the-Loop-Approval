"""
Durable State Persistence for Sentinel LangGraph.
Configures PostgresSaver backed by PostgreSQL connection pool, with local dev fallback.
"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from sentinel.config import settings
from sentinel.observability.structured_logger import logger

_GLOBAL_POOL: ConnectionPool | None = None


def get_postgres_connection_pool(uri: str) -> ConnectionPool:
    """Initialize or reuse a thread-safe psycopg connection pool."""
    global _GLOBAL_POOL
    if _GLOBAL_POOL is None:
        _GLOBAL_POOL = ConnectionPool(
            conninfo=uri,
            max_size=10,
            kwargs={"autocommit": True},
        )
    return _GLOBAL_POOL


def create_checkpointer() -> BaseCheckpointSaver:
    """
    Construct a durable checkpoint saver.
    Attempts connection to PostgreSQL. If unavailable or disabled, uses MemorySaver.
    """
    if settings.POSTGRES_URI:
        try:
            pool = get_postgres_connection_pool(settings.POSTGRES_URI)
            checkpointer = PostgresSaver(pool)
            # Setup tables if they do not exist
            checkpointer.setup()
            logger.info(f"PostgresSaver successfully connected to {settings.POSTGRES_URI.split('@')[-1]}")
            return checkpointer
        except Exception as e:
            logger.warning(
                f"PostgreSQL connection to {settings.POSTGRES_URI} failed: {e}. "
                "Falling back to MemorySaver for local graph execution."
            )

    logger.info("Using MemorySaver checkpointer.")
    return MemorySaver()
