"""
Langfuse Tracing integration for Sentinel.
Wraps LLM invocations and node executions with trace metadata, tokens, and latency tracking.
"""

import os
from typing import Any

from sentinel.config import settings
from sentinel.observability.structured_logger import logger


class SentinelTracer:
    """Manages Langfuse trace client and callbacks with graceful offline fallback."""

    def __init__(self):
        self.enabled = settings.LANGFUSE_ENABLED and bool(
            settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY
        )
        self._langfuse_client = None
        self._callback_handler = None

        if self.enabled:
            try:
                os.environ["LANGFUSE_PUBLIC_KEY"] = settings.LANGFUSE_PUBLIC_KEY or ""
                os.environ["LANGFUSE_SECRET_KEY"] = settings.LANGFUSE_SECRET_KEY or ""
                os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_HOST

                from langfuse import Langfuse
                from langfuse.callback import CallbackHandler

                self._langfuse_client = Langfuse(
                    public_key=settings.LANGFUSE_PUBLIC_KEY,
                    secret_key=settings.LANGFUSE_SECRET_KEY,
                    host=settings.LANGFUSE_HOST,
                )
                self._callback_handler = CallbackHandler()
                logger.info("Langfuse tracing successfully initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}. Tracing will be disabled.")
                self.enabled = False
        else:
            logger.info("Langfuse credentials not set or tracing disabled; operating with local tracing stub.")

    def get_langchain_callbacks(self, trace_name: str, session_id: str | None = None) -> list[Any]:
        """Return list of LangChain/LangGraph callbacks for LLM tracing."""
        if not self.enabled:
            return []

        try:
            from langfuse.callback import CallbackHandler

            return [
                CallbackHandler(
                    trace_name=trace_name,
                    session_id=session_id,
                )
            ]
        except Exception as e:
            logger.warning(f"Error obtaining Langfuse callback: {e}")
            return []

    def trace_generation(
        self,
        name: str,
        prompt: Any,
        output: Any,
        model: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Explicitly log generation telemetry to Langfuse."""
        if not self.enabled or not self._langfuse_client:
            return

        try:
            generation = self._langfuse_client.generation(
                name=name,
                model=model,
                input=str(prompt),
                output=str(output),
                metadata=metadata or {},
            )
            generation.end()
        except Exception as err:
            logger.warning(f"Failed to record Langfuse generation trace: {err}")


tracer = SentinelTracer()
