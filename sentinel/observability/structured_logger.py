"""
Structured JSON logging for Sentinel state transitions and operational metrics.
"""

import json
import logging
import sys
import time
from typing import Any

from sentinel.config import settings


class StructuredLogger:
    """Logger that outputs formatted JSON events for state transitions and operations."""

    def __init__(self, name: str = "sentinel"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

        # Avoid duplicate handlers
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(self.logger.level)
            formatter = logging.Formatter("%(message)s")
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

    def log_transition(
        self,
        from_node: str,
        to_node: str,
        thread_id: str,
        execution_time_ms: float,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record an explicit state transition between LangGraph nodes."""
        event = {
            "timestamp": time.time(),
            "event_type": "STATE_TRANSITION",
            "thread_id": thread_id,
            "from_node": from_node,
            "to_node": to_node,
            "duration_ms": round(execution_time_ms, 2),
            "metadata": metadata or {},
        }
        self.logger.info(json.dumps(event))
        return event

    def log_event(
        self,
        event_name: str,
        thread_id: str,
        level: str = "INFO",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Record a structured domain event."""
        payload = {
            "timestamp": time.time(),
            "event_type": event_name,
            "thread_id": thread_id,
            **kwargs,
        }
        log_fn = getattr(self.logger, level.lower(), self.logger.info)
        log_fn(json.dumps(payload))
        return payload

    def info(self, msg: str, **kwargs: Any) -> None:
        self.log_event("LOG_MESSAGE", thread_id="system", level="INFO", message=msg, **kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self.log_event("LOG_WARNING", thread_id="system", level="WARNING", message=msg, **kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self.log_event("LOG_ERROR", thread_id="system", level="ERROR", message=msg, **kwargs)


logger = StructuredLogger()
