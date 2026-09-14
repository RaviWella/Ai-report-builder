"""Single repair budget per chat turn (avoids validation retry loops)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .pipeline_trace import PipelineStepStatus, PipelineTracer


@dataclass
class RepairBudget:
    max_attempts: int
    used: int = 0

    def can_repair(self) -> bool:
        return self.used < self.max_attempts

    def consume(self) -> bool:
        if not self.can_repair():
            return False
        self.used += 1
        return True


def retry_on_error_with_budget(
    budget: RepairBudget,
    trace: PipelineTracer,
    *,
    tag: str,
    retry_fn: Callable[..., tuple[str, str, Optional[list], Optional[str]]],
    **kwargs,
) -> tuple[str, str, Optional[list], Optional[str]]:
    """
    Call ``retry_fn`` only if repair budget allows. Updates trace ``sql_repair`` step.
    """
    if not budget.consume():
        trace.complete(
            "sql_repair",
            PipelineStepStatus.SKIPPED,
            "No repair attempts left this turn",
        )
        return (
            kwargs.get("sql", ""),
            kwargs.get("narrative", ""),
            kwargs.get("post_process_config"),
            "Repair limit reached for this turn. Rephrase or confirm sources.",
        )

    trace.start("sql_repair", tag[:240])
    sql, narrative, post_process_config, fix_error = retry_fn(**kwargs)
    trace.note_repair(
        tag[:160] if not fix_error else f"{tag[:80]} — {fix_error[:80]}",
        success=not fix_error,
    )
    return sql, narrative, post_process_config, fix_error
