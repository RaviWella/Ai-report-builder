"""Thread-local pipeline trace listeners for SSE streaming (one turn per context)."""
from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Callable, Optional

from .pipeline_trace import PipelineTrace

PipelineListener = Callable[[PipelineTrace], None]

_listener_var: ContextVar[Optional[PipelineListener]] = ContextVar(
    "datamart_pipeline_listener",
    default=None,
)


def set_pipeline_listener(
    listener: Optional[PipelineListener],
) -> Token[Optional[PipelineListener]]:
    return _listener_var.set(listener)


def reset_pipeline_listener(token: Token[Optional[PipelineListener]]) -> None:
    _listener_var.reset(token)


def emit_pipeline_trace(trace: "PipelineTracer") -> None:
    """Push a snapshot to the active listener (if any)."""
    listener = _listener_var.get()
    if listener is None:
        return
    try:
        listener(trace.build())
    except Exception:  # noqa: BLE001
        # Streaming must not break the chat pipeline.
        import logging

        logging.getLogger("ai_services.datamart.pipeline_events").debug(
            "pipeline listener failed",
            exc_info=True,
        )


# Avoid circular import at runtime — only used for type hint above.
from typing import TYPE_CHECKING  # noqa: E402

if TYPE_CHECKING:
    from .pipeline_trace import PipelineTracer
